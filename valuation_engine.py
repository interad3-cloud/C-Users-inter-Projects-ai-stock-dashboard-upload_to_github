"""
Intelligent Valuation Engine — Gemini Adaptive 로직 + PEG · 단위무결성 · yfinance 앵커.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import yfinance as yf

from valuation import (
    FORWARD_HORIZON_LABEL,
    HIGH_GROWTH_PSR_THRESHOLD,
    OPM_PSR_THRESHOLD,
    apply_target_sanity,
    blend_to_sector_band,
    blend_with_market_per,
    compute_adaptive_per_multiple,
    compute_adaptive_psr_multiple,
    compute_peg,
    compute_psr_target_price,
    compute_y1_revenue,
    get_forward_sector_multiple_anchor,
    get_sector_per_band,
    get_sector_psr_band,
    get_sector_valuation_config,
    normalize_financial_hist,
    normalize_full_number,
    normalize_shares_outstanding,
    peg_revalidate,
    resolve_market_consensus,
    resolve_market_multiples,
    resolve_operating_margin,
    resolve_revenue_growth_pct,
    resolve_y1_eps,
    self_correct_with_consensus,
    verify_target_mcap_coherence,
)

MEGA_CAP_USD = 100e9
KRW_USD_RATE = 1300.0
OPM_PREMIUM_MAX = 0.15


@dataclass
class CompanyTypeInfo:
    code: str
    label_en: str
    label_ko: str
    model_name: str
    description: str
    selection_reason: str


@dataclass
class AdaptiveValuationResult:
    company_type: CompanyTypeInfo
    target_price: float
    valuation_model: str
    applied_model: str
    selection_reason: str
    target_multiple: float
    current_multiple: float
    valuation_note: str
    overheat_note: str = ""
    reconciliation_note: str = ""
    sector_adjustment_note: str = ""
    peg_ratio: float | None = None
    peg_verdict: str = "N/A"
    peg_note: str = ""
    market_forward_pe: float | None = None
    market_trailing_peg: float | None = None
    aggressive_target: float | None = None
    is_aggressive_scenario: bool = False
    dynamic_psr: float | None = None
    base_psr: float | None = None
    psr_cap: float | None = None
    growth_premium_applied: bool = False
    opm_premium_applied: bool = False
    opm_premium_pct: float = 0.0
    forward_per: float | None = None
    expected_eps: float | None = None
    eps_growth: float | None = None
    latest_opm: float = 0.0
    revenue_growth_pct: float = 0.0
    revenue_for_valuation: float = 0.0
    is_loss_making: bool = False
    is_growth_stock: bool = False
    use_psr: bool = False
    target_psr: float | None = None
    current_psr: float | None = None
    target_per: float = 12.5
    current_per: float = 12.5
    avg_per_3y: float = 12.5
    shares_verified: float = 0.0
    unit_integrity_ok: bool = True
    horizon_label: str = FORWARD_HORIZON_LABEL
    y1_revenue: float = 0.0
    y1_eps: float = 0.0
    y1_eps_source: str = ""
    consensus_mean: float | None = None
    consensus_low: float | None = None
    consensus_high: float | None = None
    consensus_diff_pct: float = 0.0
    consensus_correction_note: str = ""
    consensus_corrected: bool = False
    sector_anchor_note: str = ""
    forward_multiple_anchor: float = 0.0
    mcap_coherence_note: str = ""
    scenario_params: dict = field(default_factory=dict)


def _yoy_pct(values: list[float]) -> float | None:
    if len(values) < 2 or values[-2] == 0:
        return None
    return (values[-1] / values[-2]) - 1


def _market_cap_usd(info: dict) -> float:
    mcap = float(info.get("marketCap") or 0)
    if mcap <= 0:
        return 0.0
    if (info.get("currency") or "USD").upper() == "KRW":
        return mcap / KRW_USD_RATE
    return mcap


def _margin_series(rev_hist, oi_hist) -> list[float]:
    margins = []
    for yr, rev in rev_hist[-3:]:
        oi = next((v for y, v in oi_hist if y == yr), None)
        if oi is not None and rev > 0:
            margins.append(oi / rev)
    return margins


def compute_opm_premium(rev_hist, oi_hist) -> tuple[float, bool, float]:
    margins = _margin_series(rev_hist, oi_hist)
    if len(margins) < 2:
        return 1.0, False, 0.0
    delta_pp = (margins[-1] - margins[0]) * 100
    if delta_pp < 1.0:
        return 1.0, False, 0.0
    premium = float(np.clip(0.05 + delta_pp * 0.01, 0.05, OPM_PREMIUM_MAX))
    return 1.0 + premium, True, premium * 100


def should_use_psr_model(
    info: dict,
    opm: float,
    growth_pct: float,
    latest_oi: float,
) -> bool:
    """Gemini CASE A: OPM < 5% / 영업적자 / (고성장 & PSR 섹터)."""
    if latest_oi < 0 or opm < OPM_PSR_THRESHOLD:
        return True
    mcap_usd = _market_cap_usd(info)
    sector = (info.get("sector") or "").strip()
    if sector == "Technology" and mcap_usd >= MEGA_CAP_USD and latest_oi > 0:
        return False
    cfg = get_sector_valuation_config(info)
    if growth_pct > HIGH_GROWTH_PSR_THRESHOLD:
        return cfg.get("type") == "PSR" or latest_oi < 0 or opm < OPM_PSR_THRESHOLD
    return cfg.get("type") == "PSR" and growth_pct > 20.0


def select_valuation_model(
    info: dict,
    rev_growth: float,
    oi_hist: list[tuple[int, float]],
    rev_hist: list[tuple[int, float]],
    growth_pct: float,
    opm: float,
) -> tuple[str, CompanyTypeInfo]:
    latest_oi = oi_hist[-1][1] if oi_hist else 0.0
    sector = (info.get("sector") or "").strip()
    mcap_usd = _market_cap_usd(info)

    if should_use_psr_model(info, opm, growth_pct, latest_oi):
        reason = "영업적자/OPM<5%" if latest_oi < 0 or opm < OPM_PSR_THRESHOLD else f"고성장 {growth_pct:.0f}%"
        return "PSR", CompanyTypeInfo(
            code="A", label_en="Loss / High-Growth", label_ko="Type A: 적자·고성장",
            model_name="Dynamic PSR",
            description="PSR = base + max(0, 성장률-15)×0.2, 섹터 가이드 적용.",
            selection_reason=f"{reason} → Dynamic PSR",
        )

    if sector == "Technology" and mcap_usd >= MEGA_CAP_USD:
        return "FORWARD_PER", CompanyTypeInfo(
            code="T", label_en="Mega-cap Tech", label_ko="Type T: 초우량 기술주",
            model_name="Adaptive PER",
            description="PER = base + 성장률×0.5, forwardEps × PER, 섹터 20~50x.",
            selection_reason="Technology + 시총 100B+ → Adaptive PER",
        )

    return "VALUE_PER", CompanyTypeInfo(
        code="V", label_en="Value", label_ko="Type V: 일반 가치주",
        model_name="Adaptive PER",
        description="PER = base + 성장률×0.5, 섹터 min/max 클램프.",
        selection_reason="흑자·안정 — Adaptive PER",
    )


def compute_dynamic_psr(info: dict, growth_pct: float) -> float:
    return compute_adaptive_psr_multiple(info, growth_pct)


def compute_scenario_psr(info: dict, rev_growth: float, scenario: str = "Base") -> float:
    growth_pct = resolve_revenue_growth_pct(info, rev_growth)
    if scenario == "Bull":
        return compute_dynamic_psr(info, growth_pct * 1.20) * 1.06
    if scenario == "Bear":
        return compute_dynamic_psr(info, growth_pct * 0.75) * 0.94
    return compute_dynamic_psr(info, growth_pct)


def _historical_avg_per(ni_hist, current_price, shares) -> float:
    pers = []
    for _, ni in ni_hist:
        if ni > 0 and shares > 0:
            eps = ni / shares
            per = current_price / eps
            if 0 < per < 200:
                pers.append(per)
    return float(np.mean(pers[-3:])) if pers else 0.0


def _resolve_current_per(info, ni_hist, current_price, shares) -> float:
    fpe, _ = resolve_market_multiples(info)
    if fpe:
        return fpe
    v = info.get("trailingPE")
    if v and 0 < float(v) < 200:
        return float(v)
    if ni_hist and shares > 0 and ni_hist[-1][1] > 0:
        eps = ni_hist[-1][1] / shares
        if eps > 0:
            return current_price / eps
    return 15.0


def _estimate_growth_pct(ni_hist, rev_growth, info) -> float:
    return resolve_revenue_growth_pct(info, rev_growth)


def _finalize_per_target(
    info, target_per, growth_pct, expected_eps, current_price, market_fpe, market_peg,
    forward_anchor: float | None = None,
) -> tuple[float, float, float | None, str, str, str, str]:
    band = get_sector_per_band(info)
    notes: list[str] = []

    if forward_anchor and forward_anchor > 0:
        target_per = 0.45 * target_per + 0.55 * forward_anchor
        notes.append(f"12M Forward 섹터 앵커 {forward_anchor:.1f}x 반영.")

    if market_fpe:
        blended = blend_with_market_per(target_per, market_fpe, band)
        notes.append(f"forwardPE {market_fpe:.1f}x 블렌드 → {blended:.1f}x.")
        target_per = blended

    target_per, outside, sector_note = blend_to_sector_band(target_per, band, raw_weight=0.30)
    if outside:
        notes.append(sector_note)

    target_per, peg, verdict, peg_note = peg_revalidate(target_per, growth_pct, band, market_peg)
    if peg_note:
        notes.append(peg_note)

    target = target_per * expected_eps if expected_eps > 0 else current_price
    return target, target_per, peg, verdict, " ".join(notes), sector_note if outside else "", peg_note


def valuate_psr(info, revenue, growth_pct, shares, current_price, rev_hist, oi_hist, forward_psr_anchor: float):
    lo, hi = get_sector_psr_band(info)
    dynamic_psr = compute_adaptive_psr_multiple(info, growth_pct)
    if forward_psr_anchor > 0:
        dynamic_psr = 0.50 * dynamic_psr + 0.50 * forward_psr_anchor
    opm_mult, opm_applied, opm_pct = compute_opm_premium(rev_hist, oi_hist)
    dynamic_psr = float(np.clip(dynamic_psr * opm_mult, lo, hi))
    current_psr = (current_price * shares) / revenue if revenue > 0 else 0.0
    target = compute_psr_target_price(revenue, dynamic_psr, shares)

    note = (
        f"12M Forward PSR {dynamic_psr:.2f}x × Y+1 매출 "
        f"(섹터 {lo:.0f}~{hi:.0f}x, 성장 {growth_pct:.0f}%). "
        f"현재 PSR {current_psr:.2f}x."
    )
    if opm_applied:
        note += f" OPM 개선 +{opm_pct:.0f}%."
    _, outside, sector_note = blend_to_sector_band(dynamic_psr, (lo, hi))
    if outside:
        note += f" {sector_note}"
    return target, dynamic_psr, current_psr, opm_applied, opm_pct, note, sector_note if outside else ""


def valuate_adaptive_per(
    info, current_price, shares, ni_hist, rev_hist, oi_hist, y1_eps, growth_pct, forward_per_anchor,
) -> tuple[float, float, float, float, float | None, str, str, str, str, float | None, float]:
    market_fpe, market_peg = resolve_market_multiples(info)
    current_per = _resolve_current_per(info, ni_hist, current_price, shares)
    avg_per_3y = _historical_avg_per(ni_hist, current_price, shares)
    expected_eps = y1_eps

    raw_per = compute_adaptive_per_multiple(info, growth_pct)
    if forward_per_anchor > 0:
        raw_per = 0.45 * raw_per + 0.55 * forward_per_anchor
    if avg_per_3y > 0:
        raw_per = 0.40 * raw_per + 0.60 * float(np.clip(avg_per_3y, raw_per * 0.85, raw_per * 1.15))

    target, target_per, peg, verdict, blend_note, sector_note, peg_note = _finalize_per_target(
        info, raw_per, growth_pct, expected_eps, current_price, market_fpe, market_peg, forward_per_anchor,
    )
    note = f"12M Forward PER {target_per:.2f}x × Y+1 EPS {expected_eps:.2f}. {blend_note}"
    return (
        target, target_per, current_per, avg_per_3y, peg, verdict, note,
        sector_note, peg_note, market_fpe, expected_eps,
    )


def run_adaptive_valuation(
    info, series, rev_hist, oi_hist, ni_hist, roe_hist,
    rev_growth, forecast_eps_y1, avg_op_margin=0.05,
    export_weight=0.0, export_growth_trend=False,
) -> AdaptiveValuationResult | None:
    del series, roe_hist, export_weight, export_growth_trend

    rev_hist, oi_hist, ni_hist = normalize_financial_hist(rev_hist, oi_hist, ni_hist)
    if not rev_hist:
        return None

    last_revenue = rev_hist[-1][1]
    shares_raw = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    if not shares_raw:
        return None

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price or float(price) <= 0:
        return None
    current_price = float(price)
    market_cap = info.get("marketCap")

    shares, unit_ok = normalize_shares_outstanding(
        float(shares_raw), last_revenue, market_cap, current_price,
    )
    if shares <= 0:
        return None

    growth_pct = resolve_revenue_growth_pct(info, rev_growth)
    opm = resolve_operating_margin(info, rev_hist, oi_hist, avg_op_margin)
    market_fpe, market_peg = resolve_market_multiples(info)
    consensus = resolve_market_consensus(info)

    y1_revenue, y1_rev_growth = compute_y1_revenue(last_revenue, rev_growth, rev_hist)
    y1_eps, y1_eps_source = resolve_y1_eps(
        info, forecast_eps_y1, shares, ni_hist, rev_hist, avg_op_margin,
    )

    model_key, company_type = select_valuation_model(
        info, y1_rev_growth, oi_hist, rev_hist, growth_pct, opm,
    )
    latest_oi = oi_hist[-1][1] if oi_hist else 0.0
    loss_making = latest_oi < 0 or (ni_hist[-1][1] if ni_hist else 0) < 0
    is_growth = growth_pct > HIGH_GROWTH_PSR_THRESHOLD or loss_making

    use_psr = model_key == "PSR"
    forward_anchor, sector_anchor_note = get_forward_sector_multiple_anchor(
        info, use_psr, market_fpe,
    )

    applied_model = "PSR" if use_psr else "PER"
    notes: list[str] = [FORWARD_HORIZON_LABEL]
    sector_adj = peg_note = consensus_note = mcap_note = ""
    peg = None
    peg_verdict = "N/A"
    aggressive = None
    is_aggressive = False
    consensus_corrected = False
    consensus_mean = consensus.get("mean")
    consensus_diff = 0.0
    dynamic_psr = current_psr = base_psr = psr_cap = None
    opm_applied = False
    opm_pct = 0.0
    target = 0.0
    target_per = current_per = avg_per = 12.5
    expected_eps = y1_eps

    if model_key == "PSR":
        target, dynamic_psr, current_psr, opm_applied, opm_pct, note, sector_adj = valuate_psr(
            info, y1_revenue, growth_pct, shares, current_price, rev_hist, oi_hist, forward_anchor,
        )
        lo, hi = get_sector_psr_band(info)
        base_psr, psr_cap = (lo + hi) / 2, hi
        target_per = dynamic_psr or base_psr
        peg = compute_peg(current_psr, growth_pct) if current_psr else None
        if peg:
            if peg > 2.0 and dynamic_psr:
                adj_psr = float(np.clip(dynamic_psr * (2.0 / peg), lo, hi))
                target = compute_psr_target_price(y1_revenue, adj_psr, shares)
                peg_verdict, peg_note = "Overvalued", f"PSR-PEG {peg:.2f}>2.0 → {adj_psr:.1f}x."
                dynamic_psr = target_per = adj_psr
            elif peg < 0.5:
                peg_verdict = "Undervalued"
            else:
                peg_verdict = "Fair"
        notes.append(note)

    else:
        (
            target, target_per, current_per, avg_per, peg, peg_verdict, note,
            sector_adj, peg_note, market_fpe, expected_eps,
        ) = valuate_adaptive_per(
            info, current_price, shares, ni_hist, rev_hist, oi_hist,
            y1_eps, growth_pct, forward_anchor,
        )
        notes.append(note)

    target, consensus_note, consensus_mean, consensus_diff, consensus_corrected = (
        self_correct_with_consensus(
            target, info, use_psr, y1_revenue, y1_eps, shares, forward_anchor,
        )
    )
    if consensus_note:
        notes.append(consensus_note)

    target, aggressive, is_aggressive, sanity_note = apply_target_sanity(target, current_price)
    if sanity_note:
        notes.append(sanity_note)

    target, mcap_ok, mcap_note = verify_target_mcap_coherence(
        target, current_price, shares, market_cap,
    )
    unit_ok = unit_ok and mcap_ok

    if sector_anchor_note:
        notes.append(sector_anchor_note)
    if market_fpe:
        notes.append(f"yfinance forwardPE {market_fpe:.1f}x (12M).")
    if market_peg:
        notes.append(f"yfinance trailingPegRatio {market_peg:.2f}.")
    if y1_eps_source:
        notes.append(y1_eps_source)

    upside = ((target - current_price) / current_price * 100) if current_price > 0 else 0.0
    overheat = ""
    if upside < -15:
        overheat = "목표주가 대비 현재가 프리미엄 — 단기 밸류에이션 부담."
    elif is_aggressive and upside > 50:
        overheat = "가중 평균 보정 후에도 낙관적 — 실적 가시화 필요."

    return AdaptiveValuationResult(
        company_type=company_type,
        target_price=target,
        valuation_model=company_type.model_name,
        applied_model=applied_model,
        selection_reason=company_type.selection_reason,
        target_multiple=target_per,
        current_multiple=current_per,
        valuation_note=" ".join(notes),
        overheat_note=overheat,
        sector_adjustment_note=sector_adj,
        peg_ratio=peg,
        peg_verdict=peg_verdict,
        peg_note=peg_note,
        market_forward_pe=market_fpe,
        market_trailing_peg=market_peg,
        aggressive_target=aggressive,
        is_aggressive_scenario=is_aggressive,
        dynamic_psr=dynamic_psr,
        base_psr=base_psr,
        psr_cap=psr_cap,
        opm_premium_applied=opm_applied,
        opm_premium_pct=opm_pct,
        expected_eps=expected_eps,
        eps_growth=growth_pct / 100,
        latest_opm=opm,
        revenue_growth_pct=growth_pct,
        revenue_for_valuation=y1_revenue,
        is_loss_making=loss_making,
        is_growth_stock=is_growth,
        use_psr=use_psr,
        target_psr=dynamic_psr,
        current_psr=current_psr,
        target_per=target_per,
        current_per=current_per,
        avg_per_3y=avg_per,
        shares_verified=shares,
        unit_integrity_ok=unit_ok,
        horizon_label=FORWARD_HORIZON_LABEL,
        y1_revenue=y1_revenue,
        y1_eps=y1_eps,
        y1_eps_source=y1_eps_source,
        consensus_mean=consensus_mean,
        consensus_low=consensus.get("low"),
        consensus_high=consensus.get("high"),
        consensus_diff_pct=consensus_diff,
        consensus_correction_note=consensus_note,
        consensus_corrected=consensus_corrected,
        sector_anchor_note=sector_anchor_note,
        forward_multiple_anchor=forward_anchor,
        mcap_coherence_note=mcap_note,
        scenario_params={
            "model_key": model_key,
            "company_type_code": company_type.code,
            "rev_growth": y1_rev_growth,
            "growth_pct": growth_pct,
            "use_psr": use_psr,
            "target_psr": dynamic_psr,
            "target_per": target_per,
            "peg": peg,
            "horizon": FORWARD_HORIZON_LABEL,
        },
    )


def calculate_adaptive_valuation(ticker_symbol: str) -> dict:
    """
    Gemini 스타일 단독 API — yfinance info만으로 빠른 테스트.
    대시보드는 run_adaptive_valuation() + 재무제표 파이프라인 사용.
    """
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info or {}
    sector = info.get("sector", "Unknown")
    growth_pct = resolve_revenue_growth_pct(info, info.get("revenueGrowth") or 0)
    opm = resolve_operating_margin(info, [], [])
    current_price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)

    shares_raw = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or 1
    revenue = normalize_full_number(info.get("totalRevenue") or 0)
    shares, unit_ok = normalize_shares_outstanding(
        float(shares_raw), revenue, info.get("marketCap"), current_price,
    )
    market_fpe, _ = resolve_market_multiples(info)

    y1_revenue, _ = compute_y1_revenue(revenue, growth_pct / 100, [(2024, revenue)])
    y1_eps, y1_eps_source = resolve_y1_eps(info, 0, shares, [], [(2024, revenue)], opm)

    model_key, _ = select_valuation_model(
        info, growth_pct / 100, [(2024, revenue * opm)], [(2024, revenue)], growth_pct, opm,
    )
    use_psr = model_key == "PSR"
    forward_anchor, _ = get_forward_sector_multiple_anchor(info, use_psr, market_fpe)

    if use_psr:
        psr = compute_adaptive_psr_multiple(info, growth_pct)
        psr = blend_to_sector_band(psr, get_sector_psr_band(info))
        if forward_anchor:
            psr = psr * 0.6 + forward_anchor * 0.4
        target = compute_psr_target_price(y1_revenue, psr, shares)
        model_name = "Dynamic PSR (12M Forward)"
        multiple = psr
    else:
        per = compute_adaptive_per_multiple(info, growth_pct)
        per = blend_with_market_per(per, market_fpe, get_sector_per_band(info))
        if forward_anchor:
            per = per * 0.6 + forward_anchor * 0.4
        target = y1_eps * per
        model_name = "Adaptive PER (12M Forward)"
        multiple = per

    target, _, _, _ = apply_target_sanity(target, current_price)
    target, _, _, _ = self_correct_with_consensus(
        target, info, use_psr, y1_revenue, y1_eps, shares, forward_anchor,
    )
    target, _, _ = verify_target_mcap_coherence(
        target, current_price, shares, info.get("marketCap"),
    )
    upside = (target / current_price - 1) * 100 if current_price else 0

    return {
        "Ticker": ticker_symbol,
        "Sector": sector,
        "Horizon": FORWARD_HORIZON_LABEL,
        "Model": model_name,
        "Multiple": round(multiple, 2),
        "Y+1 Revenue": round(y1_revenue, 0),
        "Y+1 EPS": round(y1_eps, 2),
        "EPS Source": y1_eps_source,
        "Target Price": round(target, 2),
        "Current Price": round(current_price, 2),
        "Upside (%)": round(upside, 2),
        "Growth (%)": round(growth_pct, 2),
        "OPM (%)": round(opm * 100, 2),
        "Unit OK": unit_ok,
    }
