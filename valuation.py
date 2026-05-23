"""밸류에이션 — 단위 정규화, 섹터 멀티플 가이드, PEG 검증."""

from __future__ import annotations

import numpy as np
from functools import lru_cache

# Market Standard — 섹터별 PER/PSR 가이드라인
SECTOR_PER_BANDS: dict[str, tuple[float, float]] = {
    "Technology": (25.0, 60.0),
    "Communication Services": (20.0, 45.0),
    "Healthcare": (15.0, 35.0),
    "Consumer Cyclical": (12.0, 20.0),
    "Consumer Defensive": (12.0, 20.0),
    "Industrials": (12.0, 22.0),
    "Financial Services": (8.0, 16.0),
    "Energy": (8.0, 14.0),
    "Basic Materials": (8.0, 16.0),
    "Utilities": (12.0, 18.0),
    "Real Estate": (14.0, 24.0),
}
SECTOR_PSR_BANDS: dict[str, tuple[float, float]] = {
    "Healthcare": (8.0, 15.0),
    "Biotechnology": (8.0, 15.0),
    "Technology": (4.0, 12.0),
    "Communication Services": (3.0, 10.0),
    "Consumer Cyclical": (1.5, 4.0),
    "Consumer Defensive": (1.5, 3.5),
}
DEFAULT_PER_BAND = (12.0, 20.0)
DEFAULT_PSR_BAND = (4.0, 12.0)

# Gemini-style 섹터 앵커 (type / min / max / base)
SECTOR_VALUATION_CONFIG: dict[str, dict] = {
    "Technology": {
        "type": "PER", "min": 20.0, "max": 50.0, "base": 30.0,
        "psr_base": 10.0, "psr_cap": 20.0,
    },
    "Healthcare": {
        "type": "PSR", "min": 5.0, "max": 15.0, "base": 8.0,
        "psr_base": 8.0, "psr_cap": 20.0,
    },
    "Consumer Defensive": {
        "type": "PER", "min": 12.0, "max": 22.0, "base": 15.0,
        "psr_base": 10.0, "psr_cap": 20.0,
    },
    "Consumer Cyclical": {
        "type": "PER", "min": 12.0, "max": 20.0, "base": 15.0,
        "psr_base": 10.0, "psr_cap": 18.0,
    },
}
DEFAULT_SECTOR_CONFIG = {
    "type": "PER", "min": 15.0, "max": 25.0, "base": 18.0,
    "psr_base": 10.0, "psr_cap": 20.0,
}

PSR_GROWTH_OFFSET = 15.0
PSR_GROWTH_COEF = 0.20
PER_GROWTH_COEF = 0.50
HIGH_GROWTH_PSR_THRESHOLD = 25.0
OPM_PSR_THRESHOLD = 0.05

SEMICONDUCTOR_KEYWORDS = (
    "semiconductor", "chip", "gpu", "foundry", "memory", "nvidia", "analog",
)

GROWTH_STOCK_MIN_REV_GROWTH = 0.12
GROWTH_BULL_GROWTH_FACTOR = 1.65
GROWTH_BULL_PSR_FACTOR = 1.15

PEG_OVERVALUED = 2.0
PEG_UNDERVALUED = 0.5
MCAP_INTEGRITY_TOLERANCE = 0.05
CONSENSUS_DIVERGENCE_THRESHOLD = 0.30
FORWARD_HORIZON_LABEL = "12-Month Forward (1년 후 예상 실적)"

SECTOR_PEER_TICKERS: dict[str, list[str]] = {
    "Technology": ["MSFT", "AAPL", "AVGO", "AMD", "NVDA"],
    "Healthcare": ["LLY", "UNH", "JNJ", "ABBV"],
    "Consumer Defensive": ["KO", "PEP", "PG", "MDLZ"],
    "Consumer Cyclical": ["MCD", "NKE", "SBUX", "HD"],
    "Industrials": ["CAT", "HON", "GE", "UPS"],
    "Financial Services": ["JPM", "BAC", "V", "MA"],
    "Energy": ["XOM", "CVX", "COP", "SLB"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS"],
    "Basic Materials": ["LIN", "APD", "SHW", "ECL"],
}


def normalize_full_number(value, anchor: float | None = None) -> float:
    """yfinance Raw 재무 수치 → Full Number."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 0.0
    v = float(value)
    if v == 0:
        return 0.0
    if anchor and anchor > 0:
        if 0 < abs(v) < 1000 and anchor >= 1e7:
            v *= 1e6
        elif 0 < abs(v) < 1000 and anchor >= 1e4:
            v *= 1e3
    return v


def verify_mcap_integrity(
    shares: float,
    price: float,
    market_cap: float | None,
    tolerance: float = MCAP_INTEGRITY_TOLERANCE,
) -> tuple[float, bool]:
    """
    시가총액 / (주가 × 주식수) 최종 검증 (기본 ±5%).
    Returns: (corrected_shares, integrity_ok)
    """
    if shares <= 0 or price <= 0 or not market_cap or market_cap <= 0:
        return shares, True

    lo, hi = 1.0 - tolerance, 1.0 + tolerance

    def _ok(s: float) -> bool:
        implied = price * s
        return implied > 0 and lo <= market_cap / implied <= hi

    if _ok(shares):
        return shares, True

    for factor in (1e6, 1e3, 1e-3, 1e-6):
        adjusted = shares * factor
        if _ok(adjusted):
            return float(adjusted), False

    log_ratio = round(np.log10(market_cap / (price * shares)))
    if abs(log_ratio) >= 2:
        corrected = float(shares * (10 ** (-log_ratio)))
        return corrected, _ok(corrected)

    return shares, False


def normalize_shares_outstanding(
    shares: float,
    revenue: float,
    market_cap: float | None,
    price: float | None = None,
) -> tuple[float, bool]:
    """발행주식수 Full Number + 시가총액 교차 검증."""
    s = normalize_full_number(shares, revenue)
    if s <= 0:
        return s, True

    if s < 1000 and revenue > 1e6:
        s *= 1e6
    elif s < 1000 and market_cap and market_cap > 1e9:
        s *= 1e6

    if price and price > 0:
        s, ok = verify_mcap_integrity(s, price, market_cap)
        return s, ok
    return s, True


def normalize_financial_hist(
    rev_hist: list[tuple[int, float]],
    oi_hist: list[tuple[int, float]],
    ni_hist: list[tuple[int, float]],
) -> tuple[list[tuple[int, float]], list[tuple[int, float]], list[tuple[int, float]]]:
    if not rev_hist:
        return rev_hist, oi_hist, ni_hist
    anchor = max(abs(v) for _, v in rev_hist)
    rev_n = [(y, normalize_full_number(v, anchor)) for y, v in rev_hist]
    oi_n = [(y, normalize_full_number(v, anchor)) for y, v in oi_hist]
    ni_n = [(y, normalize_full_number(v, anchor)) for y, v in ni_hist]
    return rev_n, oi_n, ni_n


def _is_semiconductor(info: dict) -> bool:
    industry = (info.get("industry") or "").lower()
    return any(k in industry for k in SEMICONDUCTOR_KEYWORDS)


def get_sector_per_band(info: dict) -> tuple[float, float]:
    sector = (info.get("sector") or "").strip()
    if _is_semiconductor(info) or sector == "Technology":
        return SECTOR_PER_BANDS["Technology"]
    return SECTOR_PER_BANDS.get(sector, DEFAULT_PER_BAND)


def get_sector_psr_band(info: dict) -> tuple[float, float]:
    sector = (info.get("sector") or "").strip()
    industry = (info.get("industry") or "").lower()
    if any(k in industry for k in ("biotech", "diagnostic", "genomic", "pharma")):
        return SECTOR_PSR_BANDS["Biotechnology"]
    if sector in {"Healthcare", "Biotechnology"}:
        return SECTOR_PSR_BANDS["Healthcare"]
    return SECTOR_PSR_BANDS.get(sector, DEFAULT_PSR_BAND)


def sector_avg_psr(info: dict) -> float:
    lo, hi = get_sector_psr_band(info)
    return (lo + hi) / 2


def get_sector_valuation_config(info: dict) -> dict:
    """Gemini-style 섹터 앵커 설정."""
    sector = (info.get("sector") or "").strip()
    if _is_semiconductor(info):
        return SECTOR_VALUATION_CONFIG["Technology"]
    return SECTOR_VALUATION_CONFIG.get(sector, DEFAULT_SECTOR_CONFIG)


def resolve_revenue_growth_pct(info: dict, rev_growth_decimal: float) -> float:
    """yfinance revenueGrowth + 자체 추정 가중."""
    calc = rev_growth_decimal * 100
    yf = info.get("revenueGrowth")
    if yf is not None and not (isinstance(yf, float) and np.isnan(yf)):
        yf_pct = float(yf) * 100
        return float(np.clip(0.60 * yf_pct + 0.40 * calc, -15.0, 80.0))
    return float(np.clip(calc, -15.0, 50.0))


def resolve_operating_margin(info: dict, rev_hist, oi_hist, fallback: float = 0.0) -> float:
    """yfinance operatingMargins 우선, 없으면 재무제표 OPM."""
    yf = info.get("operatingMargins")
    if yf is not None and not (isinstance(yf, float) and np.isnan(yf)):
        return float(yf)
    if rev_hist and oi_hist:
        yr, rev = rev_hist[-1]
        oi = next((v for y, v in oi_hist if y == yr), None)
        if oi is not None and rev > 0:
            return float(oi / rev)
    return fallback


def compute_adaptive_psr_multiple(info: dict, growth_pct: float) -> float:
    """
    Gemini PSR: base + max(0, 성장률% - 15) × 0.2, 상한 적용.
    """
    cfg = get_sector_valuation_config(info)
    base = cfg["psr_base"]
    raw = base + max(0.0, growth_pct - PSR_GROWTH_OFFSET) * PSR_GROWTH_COEF
    raw = min(raw, cfg["psr_cap"])
    lo, hi = get_sector_psr_band(info)
    blended, _, _ = blend_to_sector_band(raw, (lo, hi), raw_weight=0.25)
    return blended


def compute_adaptive_per_multiple(info: dict, growth_pct: float) -> float:
    """
    Gemini PER: base + 성장률% × 0.5, 섹터 min/max 클램프.
    """
    cfg = get_sector_valuation_config(info)
    raw = cfg["base"] + growth_pct * PER_GROWTH_COEF
    per = float(np.clip(raw, cfg["min"], cfg["max"]))
    band = get_sector_per_band(info)
    blended, _, _ = blend_to_sector_band(per, band, raw_weight=0.30)
    return blended


def resolve_forward_eps(info: dict, forecast_eps: float, shares: float, ni_hist) -> float:
    """yfinance forwardEps 우선, 없으면 Y+1 추정 EPS."""
    eps, _ = resolve_y1_eps(info, forecast_eps, shares, ni_hist, [], 0.05, 0.21)
    return eps


def geometric_cagr(values: list[float]) -> float | None:
    if len(values) < 2 or values[0] <= 0 or values[-1] <= 0:
        return None
    n = len(values) - 1
    return (values[-1] / values[0]) ** (1 / n) - 1


def compute_y1_revenue(last_revenue: float, rev_growth_decimal: float, rev_hist: list) -> tuple[float, float]:
    """Y+1 매출 — 당해/ Y+2 혼용 금지, 보수적 성장률."""
    rev_vals = [v for _, v in rev_hist if v > 0]
    geo = geometric_cagr(rev_vals[-3:] if len(rev_vals) >= 3 else rev_vals)
    if geo is not None:
        g = float(np.clip(min(rev_growth_decimal, geo), -0.15, 0.50))
    else:
        g = float(np.clip(rev_growth_decimal, -0.15, 0.50))
    return last_revenue * (1 + g), g


def resolve_y1_eps(
    info: dict,
    forecast_eps: float,
    shares: float,
    ni_hist: list,
    rev_hist: list,
    avg_margin: float,
    tax_rate: float = 0.21,
) -> tuple[float, str]:
    """12M Forward EPS — forwardEps 우선, 없으면 3Y CAGR 보수 추정."""
    fe = info.get("forwardEps")
    if fe is not None and float(fe) > 0:
        return float(fe), "yfinance forwardEps (12M Forward)"

    if forecast_eps > 0 and shares > 0:
        return forecast_eps, "Y+1 Bottom-up EPS (12M Forward)"

    if rev_hist and shares > 0:
        last_rev = rev_hist[-1][1]
        rev_vals = [v for _, v in rev_hist if v > 0]
        geo = geometric_cagr(rev_vals[-3:] if len(rev_vals) >= 3 else rev_vals)
        g = geo if geo is not None else 0.05
        y1_rev = last_rev * (1 + g)
        eps = y1_rev * avg_margin * (1 - tax_rate) / shares
        if eps > 0:
            return eps, "3Y 기하평균 CAGR 보수 EPS (12M Forward)"

    if ni_hist and shares > 0 and ni_hist[-1][1] > 0:
        return ni_hist[-1][1] / shares * 1.05, "TTM EPS × 1.05 (12M Forward)"
    return 0.0, "EPS unavailable"


def resolve_market_consensus(info: dict) -> dict:
    """yfinance 애널리스트 컨센서스 목표가."""
    out = {"mean": None, "low": None, "high": None, "count": None}
    for key, field in (
        ("targetMeanPrice", "mean"),
        ("targetLowPrice", "low"),
        ("targetHighPrice", "high"),
        ("numberOfAnalystOpinions", "count"),
    ):
        v = info.get(key)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            try:
                out[field] = float(v)
            except (TypeError, ValueError):
                pass
    return out


def fetch_sector_peer_forward_anchor(info: dict) -> tuple[float | None, float | None, str]:
    """동종 업계 대표 종목 Forward PER/PSR 실시간 평균 (섹터별 캐시)."""
    sector = (info.get("sector") or "").strip()
    if not sector:
        return None, None, ""
    return _peer_forward_by_sector(sector)


@lru_cache(maxsize=16)
def _peer_forward_by_sector(sector: str) -> tuple[float | None, float | None, str]:
    try:
        import yfinance as yf
    except ImportError:
        return None, None, ""

    peers = SECTOR_PEER_TICKERS.get(sector, [])[:2]
    if not peers:
        return None, None, ""

    pers: list[float] = []
    psrs: list[float] = []
    for sym in peers:
        try:
            pi = yf.Ticker(sym).info or {}
            fpe = pi.get("forwardPE")
            if fpe and 0 < float(fpe) < 150:
                pers.append(float(fpe))
            rev = normalize_full_number(pi.get("totalRevenue") or 0)
            sh = pi.get("sharesOutstanding") or pi.get("impliedSharesOutstanding")
            px = pi.get("currentPrice") or pi.get("regularMarketPrice")
            if rev > 0 and sh and px:
                sh = float(sh)
                if sh < 1000:
                    sh *= 1e6
                mcap = float(px) * sh
                psrs.append(mcap / rev)
        except Exception:
            continue

    avg_per = float(np.mean(pers)) if pers else None
    avg_psr = float(np.mean(psrs)) if psrs else None
    note = f"섹터({sector}) 피어 {len(pers)}종 Forward PER 평균"
    if avg_per:
        note += f" {avg_per:.1f}x"
    return avg_per, avg_psr, note


def get_forward_sector_multiple_anchor(
    info: dict,
    use_psr: bool,
    market_fpe: float | None,
) -> tuple[float, str]:
    """12M Forward 멀티플 앵커 = 섹터 밴드 중간값 + 피어 평균 + forwardPE."""
    peer_per, peer_psr, peer_note = fetch_sector_peer_forward_anchor(info)
    if use_psr:
        lo, hi = get_sector_psr_band(info)
        mid = (lo + hi) / 2
        parts = [mid]
        if peer_psr:
            parts.append(peer_psr)
        anchor = float(np.mean(parts))
        return float(np.clip(anchor, lo, hi)), peer_note

    lo, hi = get_sector_per_band(info)
    mid = (lo + hi) / 2
    parts = [mid]
    if peer_per:
        parts.append(peer_per)
    if market_fpe:
        parts.append(float(np.clip(market_fpe, lo, hi)))
    anchor = float(np.mean(parts))
    return float(np.clip(anchor, lo, hi)), peer_note


def self_correct_with_consensus(
    target: float,
    info: dict,
    use_psr: bool,
    y1_revenue: float,
    y1_eps: float,
    shares: float,
    forward_multiple: float,
) -> tuple[float, str, float | None, float, bool]:
    """
    targetMeanPrice와 30%+ 괴리 시 Self-Correction.
    Returns: (target, note, consensus_mean, diff_pct, corrected)
    """
    consensus = resolve_market_consensus(info)
    mean = consensus.get("mean")
    if not mean or mean <= 0 or target <= 0:
        return target, "", mean, 0.0, False

    diff_pct = (target - mean) / mean * 100
    if abs(diff_pct) / 100 < CONSENSUS_DIVERGENCE_THRESHOLD:
        return (
            target,
            f"시장 컨센서스(약 {mean:,.0f}) 대비 {diff_pct:+.1f}% 범위 내.",
            mean,
            diff_pct,
            False,
        )

    sector_target = target
    if use_psr and y1_revenue > 0 and shares > 0 and forward_multiple > 0:
        sector_target = compute_psr_target_price(y1_revenue, forward_multiple, shares)
    elif y1_eps > 0 and forward_multiple > 0:
        sector_target = y1_eps * forward_multiple

    corrected = 0.50 * target + 0.30 * mean + 0.20 * sector_target
    note = (
        f"Self-Correction: 자체 목표 {target:,.0f} vs 컨센서스 {mean:,.0f} "
        f"({diff_pct:+.1f}% 괴리) → 섹터 Forward 멀티플 재참조."
    )
    new_diff = (corrected - mean) / mean * 100
    if abs(new_diff) / 100 >= CONSENSUS_DIVERGENCE_THRESHOLD:
        corrected = 0.25 * corrected + 0.75 * mean
        new_diff = (corrected - mean) / mean * 100
        note += f" 2차 보정(컨센서스 75% 가중) → {corrected:,.0f} ({new_diff:+.1f}%)."
    if abs(new_diff) / 100 >= CONSENSUS_DIVERGENCE_THRESHOLD:
        band = CONSENSUS_DIVERGENCE_THRESHOLD * 0.95
        corrected = mean * (1 + band if new_diff > 0 else 1 - band)
        new_diff = (corrected - mean) / mean * 100
        note += f" 3차 보정(컨센서스 ±{band * 100:.0f}% 밴드) → {corrected:,.0f} ({new_diff:+.1f}%)."
    elif abs(new_diff) / 100 < CONSENSUS_DIVERGENCE_THRESHOLD and "2차" not in note:
        note += f" 보정 목표 {corrected:,.0f} ({new_diff:+.1f}%)."
    return corrected, note, mean, new_diff, True


def verify_target_mcap_coherence(
    target: float,
    current_price: float,
    shares: float,
    market_cap: float | None,
) -> tuple[float, bool, str]:
    """
    [목표가×주식수] ≈ [시가총액×(1+상승여력)] 및 시가총액-주가-주식수 정합성.
    """
    if target <= 0 or current_price <= 0 or shares <= 0:
        return target, True, ""

    if market_cap and market_cap > 0:
        implied_mcap_now = current_price * shares
        if implied_mcap_now > 0:
            ratio = market_cap / implied_mcap_now
            if abs(ratio - 1.0) > MCAP_INTEGRITY_TOLERANCE:
                shares, _ = verify_mcap_integrity(shares, current_price, market_cap)

    upside = (target - current_price) / current_price
    implied_future_mcap = target * shares
    expected_future_mcap = (market_cap or current_price * shares) * (1 + upside)
    if expected_future_mcap <= 0:
        return target, True, ""

    coherence_ratio = implied_future_mcap / expected_future_mcap
    if abs(coherence_ratio - 1.0) <= MCAP_INTEGRITY_TOLERANCE:
        return target, True, "목표가×주식수 = 시총×(1+상승여력) 검증 통과."

    fixed_target = expected_future_mcap / shares
    return fixed_target, False, "단위 정합성 보정 — 목표가×주식수 재조정."


def blend_to_sector_band(
    value: float,
    band: tuple[float, float],
    raw_weight: float = 0.35,
) -> tuple[float, bool, str]:
    """
    섹터 가이드라인 밴드로 가중 보정.
    Returns: (adjusted_value, was_outside, note)
    """
    lo, hi = band
    if lo <= value <= hi:
        return value, False, ""

    clamped = float(np.clip(value, lo, hi))
    blended = raw_weight * value + (1 - raw_weight) * clamped
    blended = float(np.clip(blended, lo, hi))
    direction = "상회" if value > hi else "하회"
    note = (
        f"산출 멀티플 {value:.1f}x는 섹터 평균({lo:.0f}~{hi:.0f}x)을 {direction} — "
        f"가중치 조정 후 {blended:.1f}x 적용."
    )
    return blended, True, note


def compute_peg(per: float, growth_pct: float) -> float | None:
    """PEG = PER / EPS성장률(%). growth_pct는 25 = 25%."""
    if growth_pct <= 0 or per <= 0:
        return None
    return per / growth_pct


def peg_revalidate(
    target_per: float,
    growth_pct: float,
    band: tuple[float, float],
    market_peg: float | None = None,
) -> tuple[float, float | None, str, str]:
    """
    PEG 기반 재검증.
    Returns: (adjusted_per, peg, verdict, note)
    """
    peg = market_peg if market_peg and market_peg > 0 else compute_peg(target_per, growth_pct)
    if peg is None:
        return target_per, None, "N/A", ""

    lo, hi = band
    note = ""
    adjusted = target_per

    if peg > PEG_OVERVALUED:
        factor = PEG_OVERVALUED / peg
        adjusted = target_per * factor
        verdict = "Overvalued"
        note = (
            f"PEG {peg:.2f} > {PEG_OVERVALUED} (고평가) — "
            f"멀티플 {target_per:.1f}x → {adjusted:.1f}x 조정."
        )
    elif peg < PEG_UNDERVALUED:
        factor = min(PEG_UNDERVALUED / peg, 1.25)
        adjusted = target_per * factor
        verdict = "Undervalued"
        note = (
            f"PEG {peg:.2f} < {PEG_UNDERVALUED} (저평가) — "
            f"멀티플 {target_per:.1f}x → {adjusted:.1f}x 상향."
        )
    else:
        verdict = "Fair"

    adjusted = float(np.clip(adjusted, lo, hi))
    return adjusted, peg, verdict, note


def resolve_market_multiples(info: dict) -> tuple[float | None, float | None]:
    """yfinance trailingPegRatio, forwardPE 우선 추출."""
    forward_pe = info.get("forwardPE")
    trailing_peg = info.get("trailingPegRatio")
    fpe = float(forward_pe) if forward_pe and 0 < float(forward_pe) < 200 else None
    tpeg = float(trailing_peg) if trailing_peg and 0 < float(trailing_peg) < 10 else None
    return fpe, tpeg


def blend_with_market_per(
    calculated_per: float,
    market_forward_pe: float | None,
    band: tuple[float, float] | None = None,
) -> float:
    """계산 PER과 yfinance forwardPE 가중 평균 (시장 60%, 섹터 밴드 내 클램프)."""
    if market_forward_pe is None:
        return calculated_per
    lo, hi = band if band else (0.0, 200.0)
    mkt = float(np.clip(market_forward_pe, lo, hi))
    return 0.40 * calculated_per + 0.60 * mkt


def apply_target_sanity(
    target: float,
    current_price: float,
) -> tuple[float, float | None, bool, str]:
    """
    목표가 ±100% 초과 시 가중 평균 보정.
    Returns: (final_target, aggressive_target, is_aggressive, note)
    """
    if current_price <= 0:
        return target, None, False, ""

    upside = (target - current_price) / current_price
    if abs(upside) <= 1.0:
        return target, None, False, ""

    if upside > 1.0:
        conservative = current_price * 2.0
        weighted = 0.35 * target + 0.65 * min(target, conservative)
        note = (
            f"원시 목표가({target:,.2f})는 현재가 대비 +{upside * 100:.0f}%로 "
            "매우 공격적인 시나리오 — 보수적 관점(최대 +100%)과 가중 평균하여 "
            f"목표가 {weighted:,.2f} 제시."
        )
    else:
        conservative = current_price * 0.5
        weighted = 0.35 * target + 0.65 * max(target, conservative)
        note = (
            f"원시 목표가는 현재가 대비 {upside * 100:.0f}%로 과도한 하향 — "
            f"가중 평균 목표가 {weighted:,.2f} 제시."
        )
    return weighted, target, True, note


def is_loss_making(
    ni_hist: list[tuple[int, float]],
    oi_hist: list[tuple[int, float]] | None = None,
) -> bool:
    if ni_hist and ni_hist[-1][1] < 0:
        return True
    if oi_hist and oi_hist[-1][1] < 0:
        return True
    return False


def is_growth_stock(info: dict, revenue_growth: float, loss_making: bool) -> bool:
    if not loss_making or revenue_growth < GROWTH_STOCK_MIN_REV_GROWTH:
        return False
    sector = (info.get("sector") or "").strip()
    industry = (info.get("industry") or "").lower()
    growth_sectors = {"Healthcare", "Technology", "Communication Services"}
    growth_keywords = ("biotech", "diagnostic", "genomic", "health", "software", "cloud")
    return sector in growth_sectors or any(k in industry for k in growth_keywords)


def compute_psr_target_price(revenue: float, target_psr: float, shares: float) -> float:
    if revenue <= 0 or shares <= 0 or target_psr <= 0:
        return 0.0
    return (revenue * target_psr) / shares


def compute_investment_rating(
    base_upside: float,
    bull_upside: float | None,
    is_growth_stock: bool,
    buy_threshold: float = 20.0,
    sell_threshold: float = -10.0,
) -> tuple[str, str]:
    bull = bull_upside if bull_upside is not None else base_upside

    if is_growth_stock:
        blended = 0.45 * base_upside + 0.55 * bull
        if base_upside >= buy_threshold:
            return "매수(BUY)", f"Y+1 목표주가 대비 상승여력 {base_upside:+.1f}% — 매수(BUY) 의견."
        if base_upside < sell_threshold:
            return (
                "보유(HOLD)",
                f"현재가가 Base 목표 대비 프리미엄({base_upside:+.1f}%)이나 "
                f"Bull 시나리오({bull:+.1f}%) 감안 HOLD.",
            )
        if blended >= buy_threshold * 0.85:
            return "매수(BUY)", f"성장주 Bull 상승여력 {bull:+.1f}% 반영 — 매수(BUY)."
        return "보유(HOLD)", f"상승여력 {base_upside:+.1f}% — Bull({bull:+.1f}%) 확인 전 HOLD."

    if base_upside >= buy_threshold:
        return "매수(BUY)", f"상승여력 {base_upside:+.1f}% — 매수(BUY)."
    if base_upside < sell_threshold:
        return "매도(SELL)", f"상승여력 {base_upside:+.1f}% — 프리미엄 구간."
    return "보유(HOLD)", f"상승여력 {base_upside:+.1f}% — HOLD."
