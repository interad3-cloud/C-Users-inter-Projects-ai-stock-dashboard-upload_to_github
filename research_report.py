"""
증권사 스타일 리서치 리포트 생성 (LS증권 형식 벤치마킹).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from formatting import format_market_cap, resolve_currency
from forecasting import ForecastResult, _series_last_n, _yoy_growth
from report_generator import (
    build_forward_horizon_banner,
    build_selection_reason,
    build_valuation_footer,
    build_valuation_summary,
    enrich_compliance,
    resolve_applied_model,
)


@dataclass
class ResearchReport:
    """리서치 리포트 전체 데이터."""

    ticker: str
    company_name: str
    sector: str
    report_date: str
    report_type: str
    rating_en: str
    rating_ko: str
    target_price: float
    current_price: float
    upside_pct: float
    headline: str
    investment_points: list[str]
    recent_review_title: str
    recent_review_body: str
    sections: dict[str, str]
    financial_table: pd.DataFrame
    stock_data: dict[str, str]
    valuation_text: str
    target_per: float
    currency: str
    unit_label: str
    forecast: ForecastResult
    compliance: str = field(default_factory=str)
    valuation_footer: str = field(default_factory=str)


def _detect_currency(info: dict, ticker: str) -> tuple[str, str, float]:
    """통화·단위·나눗셈 계수."""
    cur = (info.get("currency") or "").upper()
    if cur == "KRW" or ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "KRW", "십억원", 1e9
    if cur == "USD" or not cur:
        return "USD", "백만 USD", 1e6
    return cur, "단위", 1.0


def _fmt_money(value: float, divisor: float, currency: str = "KRW") -> str:
    if pd.isna(value) or value is None:
        return "-"
    scaled = value / divisor
    if divisor >= 1e8:
        return f"{scaled:,.1f}억원"
    if divisor >= 1e6:
        return f"{scaled:,.1f}M"
    return f"{value:,.0f}"


def _fmt_price(value: float, currency: str) -> str:
    if currency == "KRW":
        return f"{value:,.0f} 원"
    return f"{value:,.2f} {currency}"


def _rating_to_en(rating: str) -> str:
    if "매수" in rating or "BUY" in rating.upper():
        return "Buy"
    if "매도" in rating or "SELL" in rating.upper():
        return "Sell"
    return "Hold"


def _build_financial_table(
    series: dict,
    forecast: ForecastResult,
    shares: float,
    current_price: float,
    target_per: float,
    divisor: float,
) -> pd.DataFrame:
    """LS 리포트 형식 주요 투자지표 (실적 + 추정)."""
    rev_hist = _series_last_n(series.get("revenue"), 3)
    oi_hist = _series_last_n(series.get("operating_income"), 3)
    ni_hist = _series_last_n(series.get("net_income"), 3)
    roe_hist = _series_last_n(series.get("roe"), 3)

    columns: list[str] = []
    rows: dict[str, list] = {
        "매출액": [],
        "영업이익": [],
        "순이익": [],
        "EPS": [],
        "증감률(%)": [],
        "PER (x)": [],
        "PBR (x)": [],
        "영업이익률 (%)": [],
        "ROE (%)": [],
    }

    # 과거 실적
    for yr, rev in rev_hist:
        col = str(yr)
        columns.append(col)
        oi = next((v for y, v in oi_hist if y == yr), np.nan)
        ni = next((v for y, v in ni_hist if y == yr), np.nan)
        roe = next((v for y, v in roe_hist if y == yr), np.nan)
        opm = (oi / rev * 100) if rev and pd.notna(oi) else np.nan
        eps = (ni / shares) if shares and pd.notna(ni) else np.nan
        per = (current_price / eps) if eps and eps > 0 else np.nan

        rows["매출액"].append(rev / divisor)
        rows["영업이익"].append(oi / divisor if pd.notna(oi) else np.nan)
        rows["순이익"].append(ni / divisor if pd.notna(ni) else np.nan)
        rows["EPS"].append(eps if pd.notna(eps) else np.nan)
        rows["증감률(%)"].append(np.nan)
        rows["PER (x)"].append(per if pd.notna(per) and 0 < per < 200 else np.nan)
        rows["PBR (x)"].append(np.nan)
        rows["영업이익률 (%)"].append(opm if pd.notna(opm) else np.nan)
        rows["ROE (%)"].append(roe if pd.notna(roe) else np.nan)

    # EPS YoY for historical
    eps_vals = rows["EPS"]
    for i in range(len(eps_vals)):
        if i > 0 and eps_vals[i - 1] and eps_vals[i] and eps_vals[i - 1] != 0:
            rows["증감률(%)"][i] = (eps_vals[i] / eps_vals[i - 1] - 1) * 100

    # 추정치
    prev_eps = eps_vals[-1] if eps_vals and pd.notna(eps_vals[-1]) else None
    for row in forecast.forecast_rows:
        col = f"{row.year}E"
        columns.append(col)
        eps = row.eps
        eps_growth = (
            ((eps / prev_eps - 1) * 100) if prev_eps and prev_eps > 0 else np.nan
        )
        prev_eps = eps
        per = target_per

        rows["매출액"].append(row.revenue / divisor)
        rows["영업이익"].append(row.operating_income / divisor)
        rows["순이익"].append(row.net_income / divisor)
        rows["EPS"].append(eps)
        rows["증감률(%)"].append(eps_growth)
        rows["PER (x)"].append(per)
        rows["PBR (x)"].append(np.nan)
        rows["영업이익률 (%)"].append(row.op_margin_pct)
        rows["ROE (%)"].append(np.nan)

    df = pd.DataFrame(rows, index=columns).T
    return df


def _build_investment_points(
    series: dict,
    forecast: ForecastResult,
    divisor: float,
) -> tuple[str, str, list[str]]:
    """핵심 투자 포인트 및 최근 실적 리뷰."""
    rev_hist = _series_last_n(series.get("revenue"), 3)
    oi_hist = _series_last_n(series.get("operating_income"), 3)

    if not rev_hist:
        return "실적 Review", "", []

    latest_yr = rev_hist[-1][0]
    rev = rev_hist[-1][1]
    oi = next((v for y, v in oi_hist if y == latest_yr), None)
    yoy_rev = _yoy_growth([v for _, v in rev_hist])
    yoy_oi = _yoy_growth([v for _, v in oi_hist]) if len(oi_hist) >= 2 else None
    opm = (oi / rev * 100) if oi and rev else None

    title = f"{latest_yr % 100}FY Review"
    body_parts = []
    rev_str = _fmt_money(rev, divisor)
    oi_str = _fmt_money(oi, divisor) if oi else "N/A"
    yoy_r = f"{yoy_rev * 100:.1f}%" if yoy_rev is not None else "N/A"
    yoy_o = f"{yoy_oi * 100:+.1f}%" if yoy_oi is not None else "N/A"
    opm_s = f"{opm:.1f}%" if opm else "N/A"

    body = (
        f"최근 연간 연결 매출액은 {rev_str}(YoY {yoy_r}), "
        f"영업이익은 {oi_str}(YoY {yoy_o}, OPM {opm_s})로 "
        f"추정 모델 기준 {'양호한' if (yoy_oi or 0) > 0 else '부진한'} 실적 흐름을 기록한 것으로 판단됨."
    )

    points = [
        f"매출액 {_fmt_money(rev, divisor)} — YoY {yoy_r} 성장률, "
        f"가중 추정 성장률 {forecast.revenue_growth_pct:.1f}% 반영됨.",
        f"영업이익률 {opm_s} → 추정 시나리오 {forecast.avg_op_margin_pct:.1f}% "
        f"(Y+2 +0.5%p, Y+3 +1.0%p 개선 가정) 전망됨.",
        f"Target {'PSR' if forecast.valuation_model == 'PSR' else 'PER'} "
        f"{forecast.target_per:.1f}x 적용 시 "
        f"Y+1 목표주가 {_fmt_price(forecast.y1_target_price, 'KRW' if divisor == 1e9 else 'USD')}, "
        f"상승여력 {forecast.upside_pct:+.1f}% 산출됨.",
        forecast.rating_comment.replace("**", ""),
    ]
    return title, body, points


def _build_analysis_sections(
    series: dict,
    forecast: ForecastResult,
    info: dict,
    divisor: float,
) -> dict[str, str]:
    """Company Analysis 본문."""
    rev_hist = _series_last_n(series.get("revenue"), 3)
    oi_hist = _series_last_n(series.get("operating_income"), 3)
    roe_hist = _series_last_n(series.get("roe"), 3)
    debt_hist = _series_last_n(series.get("debt_ratio"), 1)

    rev_yoys = []
    for i in range(1, len(rev_hist)):
        if rev_hist[i - 1][1] > 0:
            rev_yoys.append((rev_hist[i][0], (rev_hist[i][1] / rev_hist[i - 1][1] - 1) * 100))

    domestic_text = (
        "【국내·핵심 사업부 실적 분석】\n"
        + " · ".join(
            f"{yr}년 매출 YoY {g:+.1f}%" for yr, g in rev_yoys
        )
        + " 추이를 기록함. "
        if rev_yoys
        else "【핵심 사업부 실적 분석】\n"
    )
    if len(rev_hist) >= 2:
        latest_rev_g = rev_yoys[-1][1] if rev_yoys else 0
        if latest_rev_g > 5:
            domestic_text += (
                "신제품 및 판매량 확대에 따른 Top-line 성장이 견인력으로 "
                "작용한 것으로 판단됨."
            )
        elif latest_rev_g > 0:
            domestic_text += (
                "완만한 매출 성장세가 유지되고 있으며, "
                "가격·믹스 개선 여부가 향후 관건으로 평가됨."
            )
        else:
            domestic_text += (
                "매출 성장 둔화 국면이나 고정비 부담 감소에 따른 "
                "수익성 개선 가능성이 병행될 것으로 전망됨."
            )

    margin_lines = []
    for yr, rev in rev_hist:
        oi = next((v for y, v in oi_hist if y == yr), None)
        if oi and rev:
            margin_lines.append(f"{yr}년 OPM {(oi/rev*100):.1f}%")
    profitability = (
        "【수익성 개선 요인】\n"
        + ", ".join(margin_lines)
        + ". "
        + f"추정 모델상 3개년 평균 영업이익률 {forecast.avg_op_margin_pct:.1f}%를 기준으로 "
        "Y+2·Y+3 단계적 마진 개선(+0.5%p, +1.0%p)을 반영함. "
        "원가·판관비 효율화 및 규모의 경제 개선이 수익성 레버리지로 "
        "작용할 것으로 판단됨."
    )

    y1 = forecast.forecast_rows[0]
    outlook = (
        f"【향후 전망】\n"
        f"{y1.year}년(E) 연간 매출액 {_fmt_money(y1.revenue, divisor)}"
        f"(+{forecast.revenue_growth_pct:.1f}% YoY), "
        f"영업이익 {_fmt_money(y1.operating_income, divisor)} "
        f"(OPM {y1.op_margin_pct:.1f}%) 전망. "
        f"해외·신규 사업 확대 및 제품 믹스 개선을 통해 "
        f"{'매 분기 이익 개선은 충분히 가능하다고' if forecast.upside_pct > 0 else '실적 변동성 관리가 필요하다고'} "
        f"판단. "
        f"투자의견 {_rating_to_en(forecast.rating)}(유지), "
        f"목표주가 {_fmt_price(forecast.y1_target_price, info.get('currency', 'USD') or 'USD')} "
        f"(상승여력 {forecast.upside_pct:+.1f}%)."
    )

    if roe_hist and len(roe_hist) >= 2:
        roe_vals = [v for _, v in roe_hist]
        if roe_vals[-1] > roe_vals[0]:
            outlook += " ROE 개선 추세는 주주가치 제고 측면에서 긍정적으로 평가됨."

    if debt_hist and debt_hist[-1][1] >= 1.5:
        outlook += (
            " 다만 부채비율 부담으로 금리·조달비용 관리가 "
            "핵심 모니터링 요인으로 판단됨."
        )

    return {
        "국내외·핵심 사업 실적 분석": domestic_text,
        "수익성 개선 요인": profitability,
        "향후 전망": outlook,
    }


def _build_stock_data(info: dict, ticker: str, forecast: ForecastResult) -> dict[str, str]:
    """Stock Data 패널."""
    currency = resolve_currency(info, ticker)
    return {
        "티커": ticker,
        "기업유형": getattr(forecast, "company_type_label", "N/A") or "N/A",
        "밸류에이션": forecast.valuation_model,
        "섹터": info.get("sector") or "N/A",
        "산업": info.get("industry") or "N/A",
        "시가총액": format_market_cap(info.get("marketCap"), currency),
        "발행주식수": f"{forecast.shares_outstanding:,.0f}",
        "52주 최고/최저": f"{info.get('fiftyTwoWeekHigh', 'N/A')} / {info.get('fiftyTwoWeekLow', 'N/A')}",
        "배당수익률": f"{(info.get('dividendYield') or 0) * 100:.2f}%"
        if info.get("dividendYield")
        else "N/A",
        "Beta": f"{info.get('beta', 'N/A')}",
    }


def build_research_report(
    ticker: str,
    info: dict,
    series: dict,
    forecast: ForecastResult,
) -> ResearchReport:
    """LS증권 스타일 리서치 리포트 생성."""
    name = info.get("longName") or info.get("shortName") or ticker
    sector = info.get("sector") or "N/A"
    currency, unit_label, divisor = _detect_currency(info, ticker)
    today = date.today().strftime("%Y. %m. %d")

    financial_table = _build_financial_table(
        series,
        forecast,
        forecast.shares_outstanding,
        forecast.current_price,
        forecast.target_per,
        divisor,
    )

    review_title, review_body, points = _build_investment_points(series, forecast, divisor)
    sections = _build_analysis_sections(series, forecast, info, divisor)
    stock_data = _build_stock_data(info, ticker, forecast)
    type_label = getattr(forecast, "company_type_label", "") or forecast.valuation_model

    sections["Self-Adaptive 밸류에이션"] = (
        f"{type_label} · {forecast.valuation_model}. "
        f"적용 모델: {resolve_applied_model(forecast)} · "
        f"선택 이유: {build_selection_reason(forecast)}. "
        f"{forecast.valuation_note}"
    )

    if forecast.analysis:
        a = forecast.analysis
        if a.consensus.headline:
            points.insert(0, a.consensus.headline)
        if a.consensus.available:
            eps_est = a.consensus.eps_estimate or 0
            actual_eps = a.consensus.actual_eps or 0
            sections["Earnings Review"] = (
                f"{a.consensus.surprise_label}. "
                f"분석 EPS {eps_est:,.2f} 대비 실적 EPS {actual_eps:,.2f}, "
                f"서프라이즈 {a.consensus.eps_surprise_pct:+.1f}%로 산출됨. "
                + " · ".join(a.cost_structure.drivers)
            )
        points.append(a.sector_profile.description)
        sections["비용 구조 및 수익성 (COGS / SG&A)"] = a.cost_structure.summary
        sections["거시경제 민감도"] = a.macro.summary
        scenario_text = " · ".join(
            f"{s.label_ko}: 목표 {_fmt_price(s.y1_target_price, currency)} "
            f"(상승 {s.upside_pct:+.1f}%)"
            for s in a.scenarios
        )
        sections["시나리오별 목표주가"] = scenario_text

    rating_en = _rating_to_en(forecast.rating)
    headline = sections["향후 전망"].split("\n")[0].replace("【향후 전망】", "").strip() or "실적 개선 기대"

    eps_unit = "원" if currency == "KRW" else currency

    valuation = build_valuation_summary(forecast, currency)

    compliance = (
        f"자료: {name}, 리서치센터 추정 · "
        "본 자료는 고객의 증권투자를 돕기 위한 정보제공을 목적으로 제작되었음. "
        "yfinance 공개 데이터(Raw Full Number) 및 내부 Self-Adaptive 추정 모델을 기반으로 작성되었으며, "
        "정확성·완전성을 보장하지 않음. "
        "Compliance Notice: 투자 결정은 투자자 본인의 판단과 책임 하에 이루어져야 함."
    )
    compliance = enrich_compliance(compliance, forecast, info, ticker)
    valuation_footer = build_valuation_footer(forecast, info, ticker)

    return ResearchReport(
        ticker=ticker,
        company_name=name,
        sector=sector,
        report_date=today,
        report_type="Earnings Review | Company Analysis",
        rating_en=f"{rating_en} (유지)",
        rating_ko=forecast.rating,
        target_price=forecast.y1_target_price,
        current_price=forecast.current_price,
        upside_pct=forecast.upside_pct,
        headline=headline,
        investment_points=points,
        recent_review_title=review_title,
        recent_review_body=review_body,
        sections=sections,
        financial_table=financial_table,
        stock_data=stock_data,
        valuation_text=valuation,
        target_per=forecast.target_per,
        currency=currency,
        unit_label=unit_label,
        forecast=forecast,
        compliance=compliance,
        valuation_footer=valuation_footer,
    )


REPORT_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

.ls-report {
    font-family: 'Pretendard', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
    background: #FFFFFF;
    color: #191F28;
    padding: 32px 36px;
    border: 1px solid #EEF1F4;
    border-radius: 16px;
    max-width: 100%;
    margin: 0 auto 8px auto;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    line-height: 1.65;
}
.ls-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 24px;
    border-bottom: 2px solid #3182F6;
    padding-bottom: 20px;
    margin-bottom: 24px;
}
.ls-title {
    font-size: 1.45rem;
    font-weight: 800;
    color: #191F28;
    margin: 0;
    letter-spacing: -0.03em;
}
.ls-subtitle {
    font-size: 0.84rem;
    color: #8B95A1;
    margin-top: 6px;
    line-height: 1.55;
}
.ls-meta {
    text-align: right;
    font-size: 0.84rem;
    line-height: 1.75;
    color: #4E5968;
    min-width: 180px;
}
.ls-buy {
    color: #E53935;
    font-weight: 800;
    font-size: 1.15rem;
    letter-spacing: -0.02em;
}
.ls-section-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #191F28;
    border-left: 4px solid #3182F6;
    padding-left: 12px;
    margin: 28px 0 12px 0;
    letter-spacing: -0.02em;
}
.ls-body {
    font-size: 0.88rem;
    line-height: 1.85;
    color: #333D4B;
    text-align: justify;
    padding: 0 4px;
}
.ls-points {
    margin: 0;
    padding-left: 22px;
    color: #333D4B;
}
.ls-points li {
    margin-bottom: 10px;
    font-size: 0.88rem;
    line-height: 1.75;
    padding-right: 8px;
}
.ls-stock-box {
    background: #F8F9FA;
    border: 1px solid #EEF1F4;
    border-radius: 12px;
    padding: 16px 20px;
    font-size: 0.84rem;
    line-height: 1.85;
    margin: 18px 0;
    color: #333D4B;
}
.ls-footer {
    font-size: 0.74rem;
    color: #8B95A1;
    margin-top: 32px;
    border-top: 1px solid #EEF1F4;
    padding-top: 14px;
    line-height: 1.65;
}
.ls-surprise {
    background: #FFF8E1;
    border-left: 4px solid #FFB300;
    border-radius: 0 10px 10px 0;
    padding: 12px 16px;
    margin: 14px 0 18px 0;
    font-size: 0.88rem;
    font-weight: 600;
    color: #333D4B;
}
.ls-scenario-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.84rem;
    margin: 14px 0 18px 0;
    border: 1px solid #EEF1F4;
    border-radius: 12px;
    overflow: hidden;
}
.ls-scenario-table th {
    background: #F2F4F6;
    color: #191F28;
    padding: 12px 14px;
    font-weight: 700;
    border-bottom: 1px solid #EEF1F4;
}
.ls-scenario-table td {
    background: #FFFFFF;
    color: #333D4B;
    border-bottom: 1px solid #EEF1F4;
    padding: 12px 14px;
    text-align: right;
    line-height: 1.5;
}
.ls-scenario-table tbody tr:nth-child(even) td { background: #FAFBFC; }
.ls-scenario-table td:first-child { text-align: left; font-weight: 600; }
.ls-fin-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.84rem;
    margin: 14px 0 18px 0;
    border: 1px solid #EEF1F4;
    border-radius: 12px;
    overflow: hidden;
}
.ls-fin-table th {
    background: #F2F4F6;
    color: #191F28;
    padding: 12px 14px;
    text-align: right;
    font-weight: 700;
    border-bottom: 1px solid #EEF1F4;
}
.ls-fin-table td {
    background: #FFFFFF;
    color: #333D4B;
    border-bottom: 1px solid #EEF1F4;
    padding: 12px 14px;
    text-align: right;
    line-height: 1.5;
}
.ls-fin-table tbody tr:nth-child(even) td { background: #FAFBFC; }
.ls-fin-table tbody th {
    text-align: left;
    font-weight: 600;
    background: #F8F9FA;
    color: #191F28;
}
.ls-brand {
    color: #3182F6;
    font-weight: 700;
    font-size: 0.78rem;
    letter-spacing: 0.04em;
}
</style>
"""


def render_report_html(report: ResearchReport) -> str:
    """Streamlit st.markdown용 HTML."""
    points_html = "".join(f"<li>{p}</li>" for p in report.investment_points)
    sections_html = ""
    for title, body in report.sections.items():
        sections_html += f"""
        <div class="ls-section-title">{title}</div>
        <div class="ls-body">{body.replace(chr(10), '<br>')}</div>
        """

    stock_lines = " · ".join(f"{k}: {v}" for k, v in report.stock_data.items())

    fin_html = report.financial_table.round(2).to_html(
        classes="ls-fin-table",
        border=0,
        float_format=lambda x: f"{x:,.2f}" if pd.notna(x) else "-",
    )

    price_fmt = _fmt_price(report.target_price, report.currency)
    cur_fmt = _fmt_price(report.current_price, report.currency)

    surprise_html = ""
    if report.forecast.analysis and report.forecast.analysis.consensus.available:
        c = report.forecast.analysis.consensus
        surprise_html = (
            f'<div class="ls-surprise">{c.surprise_label} — '
            f"EPS 서프라이즈 {c.eps_surprise_pct:+.1f}%</div>"
        )

    scenario_html = ""
    if not report.forecast.scenario_table.empty:
        st_df = report.forecast.scenario_table
        rows = "<tr>" + "".join(f"<th>{col}</th>" for col in st_df.columns) + "</tr>"
        for _, row in st_df.iterrows():
            cells = "".join(
                f"<td>{row[col]:,.2f}</td>" if isinstance(row[col], (int, float)) else f"<td>{row[col]}</td>"
                for col in st_df.columns
            )
            rows += f"<tr>{cells}</tr>"
        scenario_html = f"""
        <div class="ls-section-title">Scenario Analysis — Bull / Base / Bear</div>
        <table class="ls-scenario-table">{rows}</table>
        """

    return f"""
{REPORT_CSS}
<div class="ls-report">
  <div class="ls-header">
    <div>
      <div class="ls-title">{report.company_name} ({report.ticker})</div>
      <div class="ls-subtitle">{report.report_type} | {report.sector} | {report.report_date}</div>
      <div class="ls-subtitle" style="color:#003366;font-weight:600;margin-top:6px;">{build_forward_horizon_banner()}</div>
    </div>
    <div class="ls-meta">
      <div class="ls-buy">{report.rating_en}</div>
      <div>목표주가 {price_fmt}</div>
      <div>현재주가 {cur_fmt}</div>
      <div>상승여력 <strong>{report.upside_pct:+.1f} %</strong></div>
    </div>
  </div>

  {surprise_html}

  <div class="ls-section-title">Earnings Review — {report.recent_review_title}</div>
  <div class="ls-body">{report.recent_review_body}</div>
  <ul class="ls-points">{points_html}</ul>

  {sections_html}

  {scenario_html}

  <div class="ls-section-title">Financial Data ({report.unit_label})</div>
  {fin_html}

  <div class="ls-section-title">Valuation — 목표주가 산출</div>
  <div class="ls-body">{report.valuation_text}</div>

  <div class="ls-stock-box"><strong>Stock Data</strong><br>{stock_lines}</div>

  <div class="ls-footer">
    <div class="ls-brand">자료: {report.company_name}, 리서치센터 추정</div>
    <div class="ls-body" style="margin-top:8px;">{report.valuation_footer}</div>
    {report.compliance}
  </div>
</div>
"""
