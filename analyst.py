"""고도화 금융 분석 — 업종·컨센서스·비용·거시·시나리오."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config import (
    CORPORATE_TAX_RATE,
    CYCLICAL_INDUSTRIES,
    CYCLICAL_KEYWORDS,
    CYCLICAL_SECTORS,
    DEFAULT_TARGET_PER,
    EXPORT_FOCUSED_KEYWORDS,
    FX_WEAK_BENEFIT_EXPORT,
    FX_WEAK_PENALTY_DOMESTIC,
    MARGIN_TREND_WEIGHT_CYCLICAL,
    SCENARIO_BEAR_GROWTH_FACTOR,
    SCENARIO_BEAR_PER_FACTOR,
    SCENARIO_BULL_GROWTH_FACTOR,
    SCENARIO_BULL_PER_FACTOR,
)
from valuation import (
    GROWTH_BULL_GROWTH_FACTOR,
    apply_target_sanity,
    get_sector_per_band,
)
from valuation_engine import compute_scenario_psr

COGS_KEYS = ["Cost Of Revenue", "Reconciled Cost Of Revenue", "Cost of Revenue"]
SGA_KEYS = [
    "Selling General And Administration",
    "Selling And Marketing Expense",
    "General And Administrative Expense",
]
REVENUE_KEYS = ["Total Revenue", "Revenue", "Operating Revenue"]


@dataclass
class SectorProfile:
    is_cyclical: bool
    sector: str
    industry: str
    model_type: str
    margin_trend_weight: float
    use_high_low_per: bool
    description: str


@dataclass
class ConsensusResult:
    available: bool
    eps_estimate: float | None
    revenue_estimate: float | None
    actual_eps: float | None
    actual_revenue: float | None
    eps_surprise_pct: float | None
    revenue_surprise_pct: float | None
    surprise_label: str
    headline: str


@dataclass
class CostStructureResult:
    cogs_trend: list[tuple[int, float]]
    sga_trend: list[tuple[int, float]]
    cogs_direction: str
    sga_direction: str
    drivers: list[str]
    summary: str


@dataclass
class MacroResult:
    export_weight: float
    domestic_weight: float
    fx_scenario_pct: float
    commodity_pressure: str
    margin_adjustment_pct: float
    summary: str


@dataclass
class ScenarioPrice:
    name: str
    label_ko: str
    target_per: float
    revenue_growth_pct: float
    y1_target_price: float
    upside_pct: float
    y1_eps: float


@dataclass
class AnalysisContext:
    sector_profile: SectorProfile
    consensus: ConsensusResult
    cost_structure: CostStructureResult
    macro: MacroResult
    scenarios: list[ScenarioPrice]
    per_high: float
    per_low: float
    per_mid: float
    margin_trend_adj: float


def _find_row(df: pd.DataFrame | None, keys: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for key in keys:
        if key in df.index:
            return df.loc[key]
    return None


def _year_from_col(col) -> int:
    if hasattr(col, "year"):
        return int(col.year)
    return int(str(col)[:4])


def classify_sector(info: dict) -> SectorProfile:
    sector = (info.get("sector") or "Unknown").strip()
    industry = (info.get("industry") or "Unknown").strip()
    combined = f"{sector} {industry}".lower()
    is_cyclical = (
        sector in CYCLICAL_SECTORS
        or industry in CYCLICAL_INDUSTRIES
        or any(k in combined for k in CYCLICAL_KEYWORDS)
    )
    is_export_consumer = any(k in combined for k in EXPORT_FOCUSED_KEYWORDS)

    if is_cyclical:
        return SectorProfile(
            is_cyclical=True,
            sector=sector,
            industry=industry,
            model_type="cyclical_trend",
            margin_trend_weight=MARGIN_TREND_WEIGHT_CYCLICAL,
            use_high_low_per=True,
            description=(
                f"사이클 업종({sector}/{industry}) — "
                "최근 분기 OPM 추세 1.2x 가중 및 PER High-Low Average 적용으로 판단됨"
            ),
        )
    if is_export_consumer:
        return SectorProfile(
            is_cyclical=False,
            sector=sector,
            industry=industry,
            model_type="export_cost_linear",
            margin_trend_weight=1.0,
            use_high_low_per=False,
            description=(
                f"내수/수출주({sector}/{industry}) — "
                "해외 매출 성장률·원가/판관비 구조 분석에 집중하는 선형 모델로 평가됨"
            ),
        )
    return SectorProfile(
        is_cyclical=False,
        sector=sector,
        industry=industry,
        model_type="linear_consumer",
        margin_trend_weight=1.0,
        use_high_low_per=False,
        description=(
            f"비사이클 업종({sector}) — "
            "수출·원가 구조 중심 선형 추정 모델이 적용되는 것으로 판단됨"
        ),
    )


def parse_earnings_estimates(estimates_df: pd.DataFrame | None, info: dict) -> ConsensusResult:
    """yfinance earnings_estimates 기반 컨센서스 비교."""
    empty = ConsensusResult(
        available=False,
        eps_estimate=None,
        revenue_estimate=None,
        actual_eps=None,
        actual_revenue=None,
        eps_surprise_pct=None,
        revenue_surprise_pct=None,
        surprise_label="데이터 없음",
        headline="컨센서스 비교 데이터 미제공",
    )
    if estimates_df is None or estimates_df.empty:
        return empty

    eps_est = rev_est = None
    try:
        if "0q" in estimates_df.index and "epsAvg" in estimates_df.columns:
            eps_est = float(estimates_df.loc["0q", "epsAvg"])
        elif "+1q" in estimates_df.index:
            eps_est = float(estimates_df.loc["+1q"].get("epsAvg", np.nan))
    except Exception:
        pass

    actual_eps = info.get("trailingEps") or info.get("epsTrailingTwelveMonths")
    if actual_eps is not None:
        actual_eps = float(actual_eps)

    rev_est = info.get("revenueEstimate") or info.get("averageAnalystRating")
    if isinstance(rev_est, str):
        rev_est = None

    eps_surprise = None
    if eps_est and actual_eps and eps_est != 0:
        eps_surprise = (actual_eps - eps_est) / abs(eps_est) * 100

    if eps_surprise is not None:
        if eps_surprise >= 5:
            label = "어닝 서프라이즈 (컨센서스 상회)"
        elif eps_surprise <= -5:
            label = "어닝 미스 (컨센서스 하회)"
        else:
            label = "컨센서스 부합"
        headline = f"{label} — EPS 서프라이즈 {eps_surprise:+.1f}%"
    else:
        label = "컨센서스 비교 제한"
        headline = "분석가 예상치 대비 실적 비교 데이터가 제한적임"

    return ConsensusResult(
        available=eps_surprise is not None,
        eps_estimate=eps_est,
        revenue_estimate=float(rev_est) if rev_est else None,
        actual_eps=actual_eps,
        actual_revenue=info.get("totalRevenue"),
        eps_surprise_pct=eps_surprise,
        revenue_surprise_pct=None,
        surprise_label=label,
        headline=headline,
    )


def analyze_cost_structure(financials: pd.DataFrame | None) -> CostStructureResult:
    """매출원가율·판관비율 3개년 추이 및 정성 드라이버."""
    rev = _find_row(financials, REVENUE_KEYS)
    cogs = _find_row(financials, COGS_KEYS)
    sga = _find_row(financials, SGA_KEYS)

    cogs_trend: list[tuple[int, float]] = []
    sga_trend: list[tuple[int, float]] = []

    if rev is not None and cogs is not None:
        cols = sorted(rev.index, reverse=True)[:3]
        for col in cols:
            r, c = rev[col], cogs[col]
            if pd.notna(r) and pd.notna(c) and r > 0:
                cogs_trend.append((_year_from_col(col), float(c / r * 100)))

    if rev is not None and sga is not None:
        cols = sorted(rev.index, reverse=True)[:3]
        for col in cols:
            r, s = rev[col], sga[col]
            if pd.notna(r) and pd.notna(s) and r > 0:
                sga_trend.append((_year_from_col(col), float(s / r * 100)))

    def _direction(trend: list[tuple[int, float]]) -> str:
        if len(trend) < 2:
            return "flat"
        return "up" if trend[-1][1] > trend[0][1] else "down" if trend[-1][1] < trend[0][1] else "flat"

    cogs_dir = _direction(cogs_trend)
    sga_dir = _direction(sga_trend)
    drivers: list[str] = []

    if cogs_dir == "down":
        drivers.append("원가율 개선(고정비 부담 감소·규모의 경제)이 수익성에 긍정적 기여")
    elif cogs_dir == "up":
        drivers.append("원재료비·매출원가율 상승 압력이 마진에 부담으로 작용")
    if sga_dir == "up":
        drivers.append("판관비(마케팅·R&D) 증가로 단기 OPM 희석 가능성 존재")
    elif sga_dir == "down":
        drivers.append("판관비율 하락이 고정비 효율화로 해석됨")
    if not drivers:
        drivers.append("비용 구조는 최근 3개년 기준 안정적 추세로 판단됨")

    cogs_str = ", ".join(f"{y}년 {v:.1f}%" for y, v in cogs_trend) if cogs_trend else "N/A"
    sga_str = ", ".join(f"{y}년 {v:.1f}%" for y, v in sga_trend) if sga_trend else "N/A"
    summary = (
        f"매출원가율(COGS) 추이: {cogs_str}. "
        f"판관비율(SG&A) 추이: {sga_str}. "
        + " · ".join(drivers)
    )

    return CostStructureResult(
        cogs_trend=cogs_trend,
        sga_trend=sga_trend,
        cogs_direction=cogs_dir,
        sga_direction=sga_dir,
        drivers=drivers,
        summary=summary,
    )


def analyze_macro_sensitivity(
    info: dict,
    series: dict,
    sector_profile: SectorProfile,
) -> MacroResult:
    """환율·원자재 가상 시나리오 및 해외 비중 추정."""
    rev_hist = series.get("revenue")
    export_weight = 0.35
    domestic_weight = 0.65

    industry = sector_profile.industry.lower()
    if any(k in industry for k in ("packaged foods", "food", "beverage", "consumer")):
        export_weight = 0.45
    if any(k in industry for k in ("semiconductor", "technology", "electronic")):
        export_weight = 0.55
    if sector_profile.sector in ("Financial Services", "Utilities", "Real Estate"):
        export_weight = 0.10
    domestic_weight = 1.0 - export_weight

    fx_scenario = 5.0
    if export_weight >= 0.40:
        margin_adj = FX_WEAK_BENEFIT_EXPORT * export_weight
        commodity = "원자재·에너지 가격 상승 시 일부 상쇄 가능"
    else:
        margin_adj = FX_WEAK_PENALTY_DOMESTIC * domestic_weight
        commodity = "내수·금리 민감 업종 — 보수적 추정 유지"

    rev_growth = None
    if rev_hist is not None and len(rev_hist) >= 2:
        vals = sorted([( _year_from_col(c), v) for c, v in rev_hist.items() if pd.notna(v)])
        if len(vals) >= 2 and vals[-2][1] > 0:
            rev_growth = (vals[-1][1] / vals[-2][1] - 1) * 100

    summary = (
        f"추정 해외 매출 비중 {export_weight*100:.0f}% / 내수 {domestic_weight*100:.0f}%. "
        f"환율 +{fx_scenario:.0f}% 약세 시나리오에서 OPM {margin_adj:+.2f}%p 조정. "
        f"{commodity}. "
    )
    if rev_growth is not None and rev_growth > 10:
        summary += "수출 성장률 확대 구간으로 해외 법인 이익 기여도 상승 전망됨."
    elif export_weight < 0.25:
        summary += "내수 비중이 높아 거시 변수 충격에 보수적 접근이 타당함."

    return MacroResult(
        export_weight=export_weight,
        domestic_weight=domestic_weight,
        fx_scenario_pct=fx_scenario,
        commodity_pressure=commodity,
        margin_adjustment_pct=margin_adj,
        summary=summary,
    )


def compute_per_range(
    net_income_hist: list[tuple[int, float]],
    current_price: float,
    shares: float,
    current_per: float,
) -> tuple[float, float, float]:
    """역사적 PER 상/하단 및 중간값."""
    pers: list[float] = []
    for _, ni in net_income_hist:
        if ni > 0 and shares > 0:
            eps = ni / shares
            per = current_price / eps
            if 0 < per < 200:
                pers.append(per)
    if len(pers) >= 2:
        return float(max(pers)), float(min(pers)), float(np.mean(pers))
    base = current_per if 0 < current_per < 200 else DEFAULT_TARGET_PER
    return base * 1.25, base * 0.75, base


def compute_quarterly_margin_trend(quarterly_financials: pd.DataFrame | None) -> float:
    """최근 분기 영업이익률 방향 (양수=개선)."""
    if quarterly_financials is None or quarterly_financials.empty:
        return 0.0
    rev = _find_row(quarterly_financials, REVENUE_KEYS)
    oi = _find_row(quarterly_financials, ["Operating Income", "EBIT"])
    if rev is None or oi is None:
        return 0.0
    cols = sorted(rev.index, reverse=True)[:4]
    margins = []
    for col in reversed(cols):
        r, o = rev[col], oi[col]
        if pd.notna(r) and pd.notna(o) and r > 0:
            margins.append(float(o / r))
    if len(margins) < 2:
        return 0.0
    return margins[-1] - margins[0]


def build_scenarios(
    base_growth: float,
    base_per: float,
    per_high: float,
    per_low: float,
    base_margin: float,
    last_revenue: float,
    shares: float,
    current_price: float,
    macro_adj: float = 0.0,
    *,
    info: dict | None = None,
    use_psr: bool = False,
    target_psr: float = 6.0,
    psr_low: float = 4.0,
    psr_high: float = 8.0,
    is_growth_stock: bool = False,
    company_type_code: str = "B",
    bps: float | None = None,
    target_pb: float | None = None,
    growth_premium: bool = False,
    margin_improving: bool = False,
) -> list[ScenarioPrice]:
    """Bull / Base / Bear — 동일 지표(PSR/PER), 성장률·멀티플만 차등."""
    bull_growth_factor = (
        GROWTH_BULL_GROWTH_FACTOR
        if is_growth_stock or company_type_code == "A"
        else SCENARIO_BULL_GROWTH_FACTOR
    )

    if use_psr:
        scenarios_cfg = [
            ("Bull", "낙관", base_growth * bull_growth_factor, None),
            ("Base", "기본", base_growth, None),
            ("Bear", "비관", base_growth * SCENARIO_BEAR_GROWTH_FACTOR, None),
        ]
    elif company_type_code == "T":
        band = get_sector_per_band(info or {})
        scenarios_cfg = [
            ("Bull", "낙관", base_growth * bull_growth_factor, base_per * SCENARIO_BULL_PER_FACTOR),
            ("Base", "기본", base_growth, base_per),
            ("Bear", "비관", base_growth * SCENARIO_BEAR_GROWTH_FACTOR, per_low),
        ]
    else:
        band = get_sector_per_band(info or {})
        scenarios_cfg = [
            ("Bull", "낙관", base_growth * bull_growth_factor, per_high * SCENARIO_BULL_PER_FACTOR),
            ("Base", "기본", base_growth, base_per),
            ("Bear", "비관", base_growth * SCENARIO_BEAR_GROWTH_FACTOR, per_low),
        ]

    results: list[ScenarioPrice] = []
    for name, label_ko, growth, multiple in scenarios_cfg:
        growth = float(np.clip(growth, -0.20, 0.50 if company_type_code == "A" else 0.35))
        rev_y1 = last_revenue * (1 + growth)

        if company_type_code == "C" and bps:
            pb = float(np.clip(multiple, 0.4, 6.0))
            target = bps * pb
            eps = 0.0
            mult_display = pb
        elif use_psr and info:
            psr = compute_scenario_psr(info, growth, name)
            target = (rev_y1 * psr) / shares if shares > 0 else 0.0
            if name == "Base":
                target, _, _, _ = apply_target_sanity(target, current_price)
            eps = 0.0
            mult_display = psr
        elif use_psr:
            psr = float(np.clip(target_psr if name == "Base" else multiple or target_psr, 1.0, psr_high))
            target = (rev_y1 * psr) / shares if shares > 0 else 0.0
            eps = 0.0
            mult_display = psr
        else:
            per_lo, per_hi = get_sector_per_band(info or {})
            per = float(np.clip(multiple, per_lo * 0.9, per_hi * 1.05))
            margin = float(np.clip(base_margin + macro_adj / 100, 0.01, 0.60))
            oi = rev_y1 * margin
            ni = oi * (1 - CORPORATE_TAX_RATE)
            eps = ni / shares if shares > 0 else 0.0
            target = eps * per
            if name == "Base":
                target, _, _, _ = apply_target_sanity(target, current_price)
            mult_display = per

        upside = (target - current_price) / current_price * 100 if current_price > 0 else 0.0
        results.append(
            ScenarioPrice(
                name=name,
                label_ko=label_ko,
                target_per=mult_display,
                revenue_growth_pct=growth * 100,
                y1_target_price=target,
                upside_pct=upside,
                y1_eps=eps,
            )
        )
    return results


def run_advanced_analysis(
    info: dict,
    series: dict,
    financials: pd.DataFrame | None,
    earnings_estimates: pd.DataFrame | None,
    quarterly_financials: pd.DataFrame | None,
    net_income_hist: list[tuple[int, float]],
    current_price: float,
    shares: float,
    current_per: float,
    base_growth: float,
    base_per: float,
    base_margin: float,
    last_revenue: float,
    *,
    use_psr: bool = False,
    target_psr: float = 6.0,
    psr_low: float = 4.0,
    psr_high: float = 8.0,
    is_growth_stock: bool = False,
    company_type_code: str = "B",
    bps: float | None = None,
    target_pb: float | None = None,
    turnaround: bool = False,
    margin_improving: bool = False,
    growth_premium: bool = False,
) -> AnalysisContext:
    """5대 고도화 로직 통합 실행."""
    sector_profile = classify_sector(info)
    consensus = parse_earnings_estimates(earnings_estimates, info)
    cost_structure = analyze_cost_structure(financials)
    macro = analyze_macro_sensitivity(info, series, sector_profile)

    per_high, per_low, per_mid = compute_per_range(
        net_income_hist, current_price, shares, current_per
    )

    if sector_profile.use_high_low_per:
        effective_per = (per_high + per_low) / 2
    else:
        effective_per = base_per

    margin_trend = compute_quarterly_margin_trend(quarterly_financials)
    margin_trend_adj = margin_trend * sector_profile.margin_trend_weight

    if not sector_profile.is_cyclical:
        export_boost = macro.export_weight * 0.04
        if sector_profile.model_type == "export_cost_linear":
            export_boost += 0.02
        base_growth = float(np.clip(base_growth + export_boost, -0.15, 0.25))
        if cost_structure.cogs_direction == "down":
            base_margin = base_margin + 0.005
        elif cost_structure.cogs_direction == "up":
            base_margin = base_margin - 0.003

    scenarios = build_scenarios(
        base_growth=base_growth,
        base_per=effective_per,
        per_high=per_high,
        per_low=per_low,
        base_margin=base_margin + margin_trend_adj,
        last_revenue=last_revenue,
        shares=shares,
        current_price=current_price,
        macro_adj=macro.margin_adjustment_pct,
        info=info,
        use_psr=use_psr,
        target_psr=target_psr,
        psr_low=psr_low,
        psr_high=psr_high,
        is_growth_stock=is_growth_stock,
        company_type_code=company_type_code,
        bps=bps,
        target_pb=target_pb,
        growth_premium=growth_premium,
        margin_improving=margin_improving,
    )

    return AnalysisContext(
        sector_profile=sector_profile,
        consensus=consensus,
        cost_structure=cost_structure,
        macro=macro,
        scenarios=scenarios,
        per_high=per_high,
        per_low=per_low,
        per_mid=per_mid,
        margin_trend_adj=margin_trend_adj,
    )
