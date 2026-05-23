"""
전통적 재무 추정(Financial Modeling) — 매출·이익·목표주가 산출.
외부 LLM API 없이 yfinance 재무 데이터만 사용.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import streamlit as st

from analyst import AnalysisContext, analyze_macro_sensitivity, classify_sector, run_advanced_analysis
from config import (
    CORPORATE_TAX_RATE,
    DEFAULT_TARGET_PER,
    FORECAST_YEARS,
    MARGIN_IMPROVEMENT_Y2,
    MARGIN_IMPROVEMENT_Y3,
    REVENUE_GROWTH_WEIGHT_CAGR,
    REVENUE_GROWTH_WEIGHT_YOY,
)
from valuation import (
    compute_investment_rating,
    normalize_financial_hist,
    normalize_shares_outstanding,
)
from valuation_engine import run_adaptive_valuation

# 투자 의견 임계값
UPSIDE_BUY_THRESHOLD = 20.0
UPSIDE_SELL_THRESHOLD = -10.0


@dataclass
class ForecastYearRow:
    """연도별 추정 결과."""

    year: int
    period_label: str
    revenue: float
    operating_income: float
    op_margin_pct: float
    net_income: float
    eps: float
    target_price: float
    expected_return_pct: float | None
    growth_rate_pct: float | None
    notes: str
    is_forecast: bool = True


@dataclass
class ForecastResult:
    """추정 엔진 전체 결과."""

    forecast_table: pd.DataFrame
    commentary: dict[str, str]
    target_per: float
    current_per: float
    avg_per_3y: float
    current_price: float
    shares_outstanding: float
    y1_target_price: float
    upside_pct: float
    rating: str
    rating_comment: str
    revenue_growth_pct: float
    avg_op_margin_pct: float
    forecast_rows: list[ForecastYearRow] = field(default_factory=list)
    historical_chart_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    forecast_chart_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    analysis: AnalysisContext | None = None
    scenario_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    valuation_model: str = "PER"
    target_psr: float | None = None
    current_psr: float | None = None
    is_loss_making: bool = False
    is_growth_stock: bool = False
    valuation_note: str = ""
    company_type: str = "B"
    company_type_label: str = ""
    overheat_note: str = ""
    growth_premium_applied: bool = False
    reconciliation_note: str = ""
    opm_pct: float = 0.0
    applied_model: str = "PER"
    selection_reason: str = ""
    opm_premium_pct: float = 0.0
    unit_integrity_ok: bool = True
    peg_ratio: float | None = None
    peg_verdict: str = "N/A"
    aggressive_target: float | None = None
    is_aggressive_scenario: bool = False
    market_forward_pe: float | None = None
    horizon_label: str = "12-Month Forward (1년 후 예상 실적)"
    y1_revenue: float = 0.0
    y1_eps: float = 0.0
    consensus_mean: float | None = None
    consensus_diff_pct: float = 0.0
    consensus_correction_note: str = ""
    forward_multiple_anchor: float = 0.0


def _year_from_col(col) -> int:
    if hasattr(col, "year"):
        return int(col.year)
    return int(str(col)[:4])


def _series_last_n(series: pd.Series | None, n: int = 3) -> list[tuple[int, float]]:
    if series is None or series.empty:
        return []
    pts = [(_year_from_col(c), float(v)) for c, v in series.items() if pd.notna(v)]
    pts.sort(key=lambda x: x[0])
    return pts[-n:]


def _geometric_cagr(values: list[float]) -> float | None:
    if len(values) < 2 or values[0] <= 0 or values[-1] <= 0:
        return None
    n = len(values) - 1
    return (values[-1] / values[0]) ** (1 / n) - 1


def _yoy_growth(values: list[float]) -> float | None:
    if len(values) < 2 or values[-2] == 0:
        return None
    return values[-1] / values[-2] - 1


def _weighted_revenue_growth(cagr: float | None, yoy: float | None) -> float:
    c = cagr if cagr is not None else 0.05
    y = yoy if yoy is not None else c
    g = REVENUE_GROWTH_WEIGHT_CAGR * c + REVENUE_GROWTH_WEIGHT_YOY * y
    return float(np.clip(g, -0.15, 0.25))


def _resolve_shares(info: dict) -> float | None:
    for key in (
        "sharesOutstanding",
        "impliedSharesOutstanding",
        "floatShares",
    ):
        v = info.get(key)
        if v and float(v) > 0:
            return float(v)
    return None


def _resolve_current_price(info: dict, price_summary: dict | None) -> float | None:
    for key in ("currentPrice", "regularMarketPrice", "previousClose"):
        v = info.get(key)
        if v and float(v) > 0:
            return float(v)
    if price_summary and price_summary.get("최근 종가"):
        return float(price_summary["최근 종가"])
    return None


def _resolve_current_per(info: dict) -> float | None:
    for key in ("trailingPE", "forwardPE"):
        v = info.get(key)
        if v is not None and isinstance(v, (int, float)) and 0 < float(v) < 200:
            return float(v)
    return None


def _historical_avg_per(
    net_income_hist: list[tuple[int, float]],
    current_price: float,
    shares: float,
) -> float | None:
    """최근 3개년 역사적 PER 평균 (동일 주가 기준 역산)."""
    pers: list[float] = []
    for _, ni in net_income_hist:
        if ni > 0 and shares > 0:
            eps = ni / shares
            per = current_price / eps
            if 0 < per < 200:
                pers.append(per)
    if pers:
        return float(np.mean(pers))
    return None


def _compute_target_per(info: dict, net_income_hist: list[tuple[int, float]], current_price: float, shares: float) -> tuple[float, float, float]:
    current_per = _resolve_current_per(info)
    avg_per_3y = _historical_avg_per(net_income_hist, current_price, shares) if shares else None

    parts = [p for p in (current_per, avg_per_3y) if p is not None]
    if parts:
        target = float(np.mean(parts))
    else:
        target = DEFAULT_TARGET_PER

    return target, current_per or DEFAULT_TARGET_PER, avg_per_3y or DEFAULT_TARGET_PER


def _generate_commentary(
    revenue_growth: float,
    margins: list[float],
    base_margin: float,
    debt_ratio: float | None,
    roe_trend: list[float] | None,
    upside: float,
    rating: str,
    analysis: AnalysisContext | None = None,
) -> dict[str, str]:
    """증권사 스타일 정성 코멘트 (규칙 기반)."""
    growth_lines: list[str] = []
    margin_improving = len(margins) >= 2 and margins[-1] > margins[0]
    low_growth = revenue_growth < 0.03

    if low_growth and margin_improving:
        growth_lines.append(
            "본 기업은 외형 성장은 정체되나 고정비 절감 및 믹스 개선을 통한 "
            "수익성 위주의 질적 성장이 예상됨."
        )
    elif revenue_growth >= 0.10:
        growth_lines.append(
            f"매출 성장률 가중 추정치 {revenue_growth * 100:.1f}%로 "
            "양호한 Top-line 모멘텀이 유지될 것으로 판단됨."
        )
    else:
        growth_lines.append(
            f"매출 성장률은 CAGR·직전년 가중({revenue_growth * 100:.1f}%)을 반영한 "
            "보수적 추정 시나리오를 적용함."
        )

    health_lines: list[str] = []
    if debt_ratio is not None and debt_ratio >= 1.5:
        health_lines.append(
            "재무 리포트상 부채부담이 존재하여 향후 금리 변동에 따른 "
            "조달비용 관리가 정성적 핵심 모니터링 요소임."
        )
    else:
        health_lines.append("부채비율은 추정 시나리오 내 재무 안정성 측면에서 통상 수준으로 평가됨.")

    if roe_trend and len(roe_trend) >= 2 and roe_trend[-1] > roe_trend[0]:
        health_lines.append(
            "자본 효율성(ROE)이 개선 추세에 있어 주주가치 제고 측면에서 긍정적 평가가 가능함."
        )

    margin_lines = [
        f"3개년 평균 영업이익률 {base_margin * 100:.1f}%를 Y+1 기준으로 적용하고, "
        f"Y+2 +{MARGIN_IMPROVEMENT_Y2 * 100:.1f}%p, Y+3 +{MARGIN_IMPROVEMENT_Y3 * 100:.1f}%p "
        "개선을 반영한 Bottom-up 추정을 적용함."
    ]

    if analysis:
        margin_lines.append(analysis.sector_profile.description)
        margin_lines.append(analysis.cost_structure.summary)
        margin_lines.append(analysis.macro.summary)
        if analysis.consensus.available:
            margin_lines.append(analysis.consensus.headline)

    if rating == "매수(BUY)":
        opinion = (
            f"12M Forward 목표주가 대비 상승여력 {upside:+.1f}%로 **매수(BUY)** 의견. "
            "실적 추정치와 밸류에이션 멀티플이 동시에 유효한 구간으로 판단됨."
        )
    elif rating == "매도(SELL)":
        opinion = (
            f"상승여력 {upside:+.1f}%로 **매도(SELL)** 의견. "
            "현재가가 추정 적정가치 대비 프리미엄 구간에 위치함."
        )
    else:
        opinion = (
            f"상승여력 {upside:+.1f}%로 **보유(HOLD)** 의견. "
            "추가 모멘텀 확인 전까지 중립적 접근이 타당함."
        )

    return {
        "재무 건전성 평가": "\n".join(health_lines),
        "성장성 분석": "\n".join(growth_lines),
        "향후 3개년 실적 전망 및 추정 소견": "\n".join(margin_lines),
        "종합 투자 의견": opinion,
    }


def run_financial_forecast(
    series: dict[str, pd.Series],
    info: dict,
    price_summary: dict | None = None,
    financials: pd.DataFrame | None = None,
    earnings_estimates: pd.DataFrame | None = None,
    quarterly_financials: pd.DataFrame | None = None,
) -> ForecastResult | None:
    """
    전체 재무 추정 파이프라인 실행.
    """
    rev_hist = _series_last_n(series.get("revenue"), 3)
    oi_hist = _series_last_n(series.get("operating_income"), 3)
    ni_hist = _series_last_n(series.get("net_income"), 3)
    rev_hist, oi_hist, ni_hist = normalize_financial_hist(rev_hist, oi_hist, ni_hist)
    debt_hist = _series_last_n(series.get("debt_ratio"), 1)
    roe_hist = _series_last_n(series.get("roe"), 3)

    if len(rev_hist) < 2:
        return None

    rev_values = [v for _, v in rev_hist]
    cagr = _geometric_cagr(rev_values)
    yoy = _yoy_growth(rev_values)
    rev_growth = _weighted_revenue_growth(cagr, yoy)

    # 영업이익률 (최근 3개년)
    op_margins: list[float] = []
    for yr, rev in rev_hist:
        oi_match = next((v for y, v in oi_hist if y == yr), None)
        if oi_match is not None and rev > 0:
            op_margins.append(oi_match / rev)
    if not op_margins:
        op_margins = [0.12]
    avg_op_margin = float(np.mean(op_margins))

    base_year = rev_hist[-1][0]
    last_revenue = rev_hist[-1][1]

    shares_raw = _resolve_shares(info)
    current_price = _resolve_current_price(info, price_summary)
    if not shares_raw or not current_price:
        return None

    shares, unit_ok = normalize_shares_outstanding(
        shares_raw,
        last_revenue,
        info.get("marketCap"),
        current_price,
    )
    if shares <= 0:
        return None

    # Y+1 EPS 사전 추정 (Type B Forward PER용)
    prelim_margin = float(np.clip(avg_op_margin, 0.01, 0.60))
    prelim_rev_y1 = last_revenue * (1 + rev_growth)
    prelim_eps_y1 = (prelim_rev_y1 * prelim_margin * (1 - CORPORATE_TAX_RATE)) / shares

    sector_profile = classify_sector(info)
    macro_pre = analyze_macro_sensitivity(info, series, sector_profile)
    export_weight = macro_pre.export_weight
    export_trend = export_weight >= 0.40

    adaptive = run_adaptive_valuation(
        info=info,
        series=series,
        rev_hist=rev_hist,
        oi_hist=oi_hist,
        ni_hist=ni_hist,
        roe_hist=roe_hist,
        rev_growth=rev_growth,
        forecast_eps_y1=prelim_eps_y1,
        avg_op_margin=avg_op_margin,
        export_weight=export_weight,
        export_growth_trend=export_trend,
    )
    if adaptive is None:
        return None

    use_psr = adaptive.use_psr
    target_psr = adaptive.target_psr
    current_psr = adaptive.current_psr
    target_per = adaptive.target_per
    current_per = adaptive.current_per
    avg_per_3y = adaptive.avg_per_3y
    loss_making = adaptive.is_loss_making
    growth_stock = adaptive.is_growth_stock
    val_note = adaptive.valuation_note
    if adaptive.reconciliation_note:
        val_note = f"{val_note} {adaptive.reconciliation_note}"
    if adaptive.overheat_note:
        val_note = f"{val_note} {adaptive.overheat_note}"

    if growth_stock and adaptive.company_type.code == "A":
        rev_growth = float(np.clip(rev_growth, -0.15, 0.50))

    margin_improving = len(op_margins) >= 2 and op_margins[-1] > op_margins[0]

    analysis = run_advanced_analysis(
        info=info,
        series=series,
        financials=financials,
        earnings_estimates=earnings_estimates,
        quarterly_financials=quarterly_financials,
        net_income_hist=ni_hist,
        current_price=current_price,
        shares=shares,
        current_per=current_per,
        base_growth=rev_growth,
        base_per=target_per,
        base_margin=avg_op_margin,
        last_revenue=last_revenue,
        use_psr=use_psr,
        target_psr=target_psr or adaptive.base_psr or 6.0,
        psr_low=(adaptive.base_psr or 4.0) * 0.75,
        psr_high=adaptive.psr_cap or 10.0,
        is_growth_stock=growth_stock,
        company_type_code=adaptive.company_type.code,
        growth_premium=adaptive.growth_premium_applied,
        margin_improving=margin_improving,
    )
    avg_op_margin = float(np.clip(avg_op_margin + analysis.margin_trend_adj, 0.01, 0.60))

    if adaptive.company_type.code == "T":
        rev_growth = float(np.clip(rev_growth, -0.10, 0.35))
    elif not use_psr and analysis.sector_profile.use_high_low_per and adaptive.company_type.code == "V":
        target_per = analysis.per_mid
        rev_growth = float(np.clip(rev_growth, -0.15, 0.30))
    elif not use_psr:
        rev_growth = float(np.clip(
            rev_growth + analysis.macro.export_weight * 0.015, -0.15, 0.25
        ))

    forecast_rows: list[ForecastYearRow] = []
    prev_revenue = last_revenue

    for i in range(1, FORECAST_YEARS + 1):
        year = base_year + i
        if i == 1:
            revenue = adaptive.y1_revenue or last_revenue * (1 + rev_growth)
            margin = avg_op_margin
        else:
            revenue = prev_revenue * (1 + rev_growth)
            margin = avg_op_margin + (MARGIN_IMPROVEMENT_Y2 if i == 2 else 0) + (
                MARGIN_IMPROVEMENT_Y3 if i == 3 else 0
            )
        margin = float(np.clip(margin, 0.01, 0.60))
        operating_income = revenue * margin
        net_income = operating_income * (1 - CORPORATE_TAX_RATE)
        eps = (adaptive.y1_eps if i == 1 and adaptive.y1_eps else net_income / shares) if shares > 0 else 0.0

        if i == 1:
            target_price = adaptive.target_price
            if use_psr and adaptive.dynamic_psr:
                notes = (
                    f"12M Forward PSR {adaptive.dynamic_psr:.2f}x × Y+1 매출 "
                    f"(성장 {adaptive.revenue_growth_pct:.1f}%)"
                )
            else:
                notes = (
                    f"12M Forward PER {target_per:.1f}x × Y+1 EPS {eps:.2f} "
                    f"({adaptive.horizon_label})"
                )
        else:
            target_price = 0.0
            notes = f"Y+{i} 참고 추정 — 목표주가 산출은 Y+1(12M Forward) 기준만 사용."

        expected_return = ((target_price - current_price) / current_price * 100) if i == 1 else None

        forecast_rows.append(
            ForecastYearRow(
                year=year,
                period_label=f"Y+{i}",
                revenue=revenue,
                operating_income=operating_income,
                op_margin_pct=margin * 100,
                net_income=net_income,
                eps=eps,
                target_price=target_price,
                expected_return_pct=expected_return,
                growth_rate_pct=rev_growth * 100,
                notes=notes,
                is_forecast=True,
            )
        )
        prev_revenue = revenue

    y1 = forecast_rows[0]
    if adaptive.target_price > 0:
        y1.target_price = adaptive.target_price
        y1.expected_return_pct = (
            (adaptive.target_price - current_price) / current_price * 100
        )
        forecast_rows[0] = y1
    upside = ((y1.target_price - current_price) / current_price) * 100
    bull_upside = analysis.scenarios[0].upside_pct if analysis.scenarios else upside
    rating, rating_detail = compute_investment_rating(
        upside, bull_upside, growth_stock,
        buy_threshold=UPSIDE_BUY_THRESHOLD,
        sell_threshold=UPSIDE_SELL_THRESHOLD,
    )
    if adaptive.overheat_note and upside < 0:
        rating_detail = f"{rating_detail} {adaptive.overheat_note}"

    debt_ratio = debt_hist[-1][1] if debt_hist else None
    roe_vals = [v for _, v in roe_hist] if roe_hist else None
    commentary = _generate_commentary(
        rev_growth,
        op_margins,
        avg_op_margin,
        debt_ratio,
        roe_vals,
        upside,
        rating,
        analysis,
    )
    commentary["종합 투자 의견"] = rating_detail

    mult_col = (
        "Target PSR" if use_psr
        else "Target PER"
    )
    scenario_table = pd.DataFrame(
        [
            {
                "시나리오": s.label_ko,
                mult_col: s.target_per,
                "매출성장률(%)": s.revenue_growth_pct,
                "Y+1 EPS": s.y1_eps if not use_psr else np.nan,
                "Y+1 목표주가": s.y1_target_price,
                "상승여력(%)": s.upside_pct,
            }
            for s in analysis.scenarios
        ]
    )

    table_records = []
    for row in forecast_rows:
        table_records.append(
            {
                "연도": f"{row.year} ({row.period_label})",
                "매출액": row.revenue,
                "영업이익": row.operating_income,
                "이익률(%)": row.op_margin_pct,
                "추정 근거 및 비고": row.notes,
                "예상 EPS": row.eps,
                "적정 예상 주가": row.target_price,
                "현재가 대비 기대수익률(%)": row.expected_return_pct,
            }
        )

    forecast_table = pd.DataFrame(table_records)

    hist_records = []
    for yr, rev in rev_hist:
        oi = next((v for y, v in oi_hist if y == yr), np.nan)
        margin = (oi / rev * 100) if rev and pd.notna(oi) else np.nan
        hist_records.append(
            {
                "연도": str(yr),
                "구분": "실적",
                "매출액": rev,
                "영업이익": oi,
                "이익률(%)": margin,
            }
        )

    fc_records = []
    for row in forecast_rows:
        fc_records.append(
            {
                "연도": str(row.year),
                "구분": "추정",
                "매출액": row.revenue,
                "영업이익": row.operating_income,
                "이익률(%)": row.op_margin_pct,
            }
        )

    historical_chart_df = pd.DataFrame(hist_records)
    forecast_chart_df = pd.DataFrame(fc_records)

    return ForecastResult(
        forecast_table=forecast_table,
        commentary=commentary,
        target_per=target_per,
        current_per=current_per,
        avg_per_3y=avg_per_3y,
        current_price=current_price,
        shares_outstanding=shares,
        y1_target_price=y1.target_price,
        upside_pct=upside,
        rating=rating,
        rating_comment=commentary["종합 투자 의견"],
        revenue_growth_pct=rev_growth * 100,
        avg_op_margin_pct=avg_op_margin * 100,
        forecast_rows=forecast_rows,
        historical_chart_df=historical_chart_df,
        forecast_chart_df=forecast_chart_df,
        analysis=analysis,
        scenario_table=scenario_table,
        valuation_model=adaptive.valuation_model,
        target_psr=target_psr,
        current_psr=current_psr,
        is_loss_making=loss_making,
        is_growth_stock=growth_stock,
        valuation_note=val_note,
        company_type=adaptive.company_type.code,
        company_type_label=adaptive.company_type.label_ko,
        overheat_note=adaptive.overheat_note,
        growth_premium_applied=adaptive.growth_premium_applied,
        reconciliation_note=adaptive.reconciliation_note,
        opm_pct=adaptive.latest_opm * 100,
        applied_model=adaptive.applied_model,
        selection_reason=adaptive.selection_reason,
        opm_premium_pct=adaptive.opm_premium_pct,
        unit_integrity_ok=adaptive.unit_integrity_ok,
        peg_ratio=adaptive.peg_ratio,
        peg_verdict=adaptive.peg_verdict,
        aggressive_target=adaptive.aggressive_target,
        is_aggressive_scenario=adaptive.is_aggressive_scenario,
        market_forward_pe=adaptive.market_forward_pe,
        horizon_label=adaptive.horizon_label,
        y1_revenue=adaptive.y1_revenue,
        y1_eps=adaptive.y1_eps,
        consensus_mean=adaptive.consensus_mean,
        consensus_diff_pct=adaptive.consensus_diff_pct,
        consensus_correction_note=adaptive.consensus_correction_note,
        forward_multiple_anchor=adaptive.forward_multiple_anchor,
    )


@st.cache_data(ttl=3600, show_spinner="재무 추정·목표주가 계산 중...")
def run_cached_financial_forecast(ticker: str, period: str) -> ForecastResult | None:
    """티커·기간별 추정 결과 캐시 — Cloud 재접속·탭 전환 시 재계산 방지."""
    from data_loader import load_analysis_data
    from financials import extract_annual_series

    bundle = load_analysis_data(ticker, period)
    series = extract_annual_series(
        bundle["fin_data"].get("financials"),
        bundle["fin_data"].get("balance_sheet"),
        bundle["fin_data"].get("cashflow"),
    )
    return run_financial_forecast(
        series,
        bundle["info"],
        financials=bundle["fin_data"].get("financials"),
        earnings_estimates=bundle["earnings_est"],
        quarterly_financials=bundle["quarterly_fin"],
    )
