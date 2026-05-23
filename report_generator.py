"""
리포트 생성기 — 12M Forward · 컨센서스 교차검증 · 섹터 앵커.
"""

from __future__ import annotations

from formatting import format_market_cap, format_price, resolve_currency
from forecasting import ForecastResult

FORWARD_HORIZON_BANNER = "목표주가 산출 기준: 12-Month Forward (1년 후 예상 실적)"


def resolve_applied_model(forecast: ForecastResult) -> str:
    applied = getattr(forecast, "applied_model", "") or ""
    if applied in ("PSR", "PER"):
        return applied
    if forecast.company_type == "A" or forecast.valuation_model == "Dynamic PSR":
        return "PSR"
    return "PER"


def build_forward_horizon_banner() -> str:
    return FORWARD_HORIZON_BANNER


def build_selection_reason(forecast: ForecastResult) -> str:
    reason = getattr(forecast, "selection_reason", "") or ""
    if reason:
        return reason
    return getattr(forecast, "company_type_label", "") or forecast.valuation_model


def build_consensus_footer(forecast: ForecastResult, info: dict, ticker: str) -> str:
    currency = resolve_currency(info, ticker)
    mean = getattr(forecast, "consensus_mean", None)
    diff = getattr(forecast, "consensus_diff_pct", 0.0)
    anchor = getattr(forecast, "forward_multiple_anchor", 0.0)
    model = resolve_applied_model(forecast)

    if mean and mean > 0:
        mean_fmt = format_price(mean, currency)
        return (
            f"본 목표주가는 시장 컨센서스(약 {mean_fmt}) 대비 {diff:+.1f}% 범위 내에서 산출되었으며, "
            f"섹터 평균 Forward {model} ({anchor:.1f}배)을 참조하였습니다."
        )
    return (
        f"본 목표주가는 섹터 평균 Forward {model} ({anchor:.1f}배)과 "
        "Y+1 예상 실적을 결합하여 산출되었습니다."
    )


def build_valuation_footer(forecast: ForecastResult, info: dict, ticker: str) -> str:
    currency = resolve_currency(info, ticker)
    model = resolve_applied_model(forecast)
    reason = build_selection_reason(forecast)
    mcap = format_market_cap(info.get("marketCap"), currency)
    unit_ok = getattr(forecast, "unit_integrity_ok", True)
    integrity = "±5% 검증 통과" if unit_ok else "시가총액·목표가×주식수 교차검증 후 보정"

    lines = [
        FORWARD_HORIZON_BANNER,
        build_consensus_footer(forecast, info, ticker),
        f"적용 모델: {model} · 선택 이유: {reason}",
        f"Y+1 매출: {getattr(forecast, 'y1_revenue', 0):,.0f} · Y+1 EPS: {getattr(forecast, 'y1_eps', 0):,.2f}",
        f"시가총액: {mcap} · 발행주식수: {forecast.shares_outstanding:,.0f}주 · {integrity}",
    ]

    peg = getattr(forecast, "peg_ratio", None)
    if peg is not None:
        lines.append(f"PEG {peg:.2f} ({getattr(forecast, 'peg_verdict', 'N/A')})")

    if getattr(forecast, "consensus_correction_note", ""):
        lines.append(forecast.consensus_correction_note)

    return " · ".join(lines)


def build_valuation_summary(forecast: ForecastResult, currency: str) -> str:
    type_label = getattr(forecast, "company_type_label", "") or forecast.valuation_model
    price_fmt = format_price(forecast.y1_target_price, currency)
    cur_fmt = format_price(forecast.current_price, currency)
    model = resolve_applied_model(forecast)

    body = f"{FORWARD_HORIZON_BANNER}. "
    if model == "PSR" and forecast.target_psr:
        body += (
            f"[{type_label}] 12M Forward 목표주가 {price_fmt}. "
            f"PSR {forecast.target_psr:.2f}x × Y+1 매출. "
            f"{forecast.valuation_note} "
            f"현재주가 {cur_fmt} 대비 {forecast.upside_pct:+.1f}%."
        )
    else:
        eps = getattr(forecast, "y1_eps", 0) or (
            forecast.forecast_rows[0].eps if forecast.forecast_rows else 0
        )
        body += (
            f"[{type_label}] 12M Forward 목표주가 {price_fmt}. "
            f"{forecast.valuation_model} {forecast.target_per:.2f}x × Y+1 EPS {eps:,.2f} {currency}. "
            f"{forecast.valuation_note} "
            f"상승여력 {forecast.upside_pct:+.1f}%."
        )

    if getattr(forecast, "is_aggressive_scenario", False):
        body += " 공격적 시나리오는 보수적 가중 평균으로 조정함."
    if forecast.overheat_note:
        body += f" {forecast.overheat_note}"
    return body


def enrich_compliance(compliance: str, forecast: ForecastResult, info: dict, ticker: str) -> str:
    return f"{compliance}\n\n{build_valuation_footer(forecast, info, ticker)}"
