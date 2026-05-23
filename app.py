"""주식 분석 대시보드 — Streamlit 메인 앱."""

from __future__ import annotations

import streamlit as st

from charts import (
    build_forecast_bar_chart,
    build_price_chart,
    build_revenue_profit_bar,
    build_scenario_chart,
    build_target_price_chart,
)
from config import DISCLAIMER_KO, PERIOD_OPTIONS
from formatting import format_percent, format_price, format_ratio, resolve_currency
from data_loader import (
    TickerNotFoundError,
    fetch_earnings_estimates,
    fetch_financial_statements,
    fetch_price_history,
    fetch_quarterly_financials,
    fetch_ticker_info,
    validate_ticker,
)
from financials import build_metrics_table, compute_annual_amounts_chart, extract_annual_series
from forecasting import run_financial_forecast
from indicators import enrich_price_data, summarize_technical_indicators
from research_report import build_research_report, render_report_html
from report_pdf import generate_report_pdf
from ui_components import inject_global_styles, render_stock_header_card, render_technical_signals_panel

st.set_page_config(
    page_title="주식 분석 대시보드",
    page_icon="📈",
    layout="wide",
)

if "analysis_ticker" not in st.session_state:
    st.session_state.analysis_ticker = None
if "analysis_period_label" not in st.session_state:
    st.session_state.analysis_period_label = None


def render_header(info: dict, ticker: str) -> str:
    """상단 종목 카드 — 표시 통화 반환."""
    return render_stock_header_card(info, ticker)


def render_research_report_tab(
    ticker: str,
    info: dict,
    series: dict,
    metrics_df,
    forecast_result,
) -> None:
    """증권사 리포트 — 2단 레이아웃."""
    st.subheader("증권사 리포트")
    st.caption("LS증권 Earnings Review 형식 · 업종·컨센서스·시나리오 분석 통합")

    if forecast_result is None:
        st.warning("리포트 생성에 필요한 추정 데이터가 없습니다.")
        return

    report = build_research_report(ticker, info, series, forecast_result)
    currency = resolve_currency(info, ticker)

    st.caption(getattr(forecast_result, "horizon_label", "12-Month Forward (1년 후 예상 실적)"))

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("투자의견", report.rating_en.split()[0])
    k2.metric("12M Forward 목표주가", format_price(report.target_price, currency))
    k3.metric("현재주가", format_price(report.current_price, currency))
    k4.metric("상승여력", format_percent(report.upside_pct, signed=True))
    if forecast_result.analysis and forecast_result.analysis.consensus.available:
        k5.metric(
            "어닝 서프라이즈",
            f"{forecast_result.analysis.consensus.eps_surprise_pct:+.1f}%",
        )
    else:
        k5.metric("컨센서스", "N/A")

    if forecast_result.analysis and forecast_result.analysis.consensus.available:
        st.info(f"📊 **{forecast_result.analysis.consensus.surprise_label}**")

    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.markdown("#### Stock Data & Metrics")
        for k, v in report.stock_data.items():
            st.markdown(f"**{k}** · {v}")

        if forecast_result.analysis:
            st.markdown(f"**업종 모델** · {forecast_result.analysis.sector_profile.model_type}")
            st.caption(forecast_result.analysis.sector_profile.description)

        st.markdown("#### 시나리오별 목표주가")
        if not forecast_result.scenario_table.empty:
            fmt_cols = {
                "매출성장률(%)": "{:.1f}",
                "Y+1 EPS": "{:,.2f}",
                "Y+1 목표주가": "{:,.2f}",
                "상승여력(%)": "{:+.1f}",
            }
            if "Target PSR" in forecast_result.scenario_table.columns:
                fmt_cols["Target PSR"] = "{:.2f}"
            if "Target PER" in forecast_result.scenario_table.columns:
                fmt_cols["Target PER"] = "{:.1f}"
            st.dataframe(
                forecast_result.scenario_table.style.format(fmt_cols),
                use_container_width=True,
                key="report_scenario_table",
            )
            if forecast_result.analysis:
                fig_sc = build_scenario_chart(
                    forecast_result.analysis.scenarios,
                    forecast_result.current_price,
                )
                st.plotly_chart(fig_sc, use_container_width=True, key="report_scenario_chart")

        bar6 = build_forecast_bar_chart(
            forecast_result.historical_chart_df,
            forecast_result.forecast_chart_df,
        )
        if bar6:
            st.plotly_chart(bar6, use_container_width=True, key="report_forecast_bar6")

        if not metrics_df.empty:
            st.markdown("#### 주요 재무 지표")
            st.dataframe(
                metrics_df.style.format("{:,.2f}", na_rep="-"),
                use_container_width=True,
                key="report_metrics_table",
            )

        try:
            pdf_bytes = generate_report_pdf(report)
            st.download_button(
                label="📄 PDF 다운로드",
                data=pdf_bytes,
                file_name=f"{ticker.replace('.', '_')}_research_report.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
                key="report_pdf_download",
            )
        except Exception as exc:
            st.error(f"PDF 생성 오류: {exc}")

    with col_right:
        st.markdown("#### Professional Analysis Report")
        st.markdown(render_report_html(report), unsafe_allow_html=True)


def render_forecast_tab(
    series: dict,
    info: dict,
    metrics_df,
    forecast_result=None,
    currency: str = "USD",
) -> None:
    """향후 3개년 실적 전망 및 추정 소견 탭."""
    st.subheader("향후 3개년 실적 전망 및 추정 소견")
    st.caption(
        "증권사 리서치 방식의 **전통적 재무 추정 모델** "
        "(CAGR·가중 성장률, 영업이익률 시나리오, Target PER)을 자동 적용합니다."
    )

    result = forecast_result
    if result is None:
        with st.spinner("재무 추정 모델을 실행하는 중..."):
            result = run_financial_forecast(series, info)

    if result is None:
        st.warning(
            "추정에 필요한 재무 데이터(매출·주가·발행주식수)가 부족합니다. "
            "다른 티커를 시도하거나 재무제표 탭에서 데이터 제공 여부를 확인해 주세요."
        )
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("현재 주가", format_price(result.current_price, currency))
    m2.metric("12M Forward 목표주가", format_price(result.y1_target_price, currency))
    m3.metric("기대 수익률 (12M)", format_percent(result.upside_pct, signed=True))

    st.caption(getattr(result, "horizon_label", "12-Month Forward (1년 후 예상 실적)"))

    if result.valuation_model == "Dynamic PSR" or result.company_type == "A":
        st.info(
            f"**{result.company_type_label}** · **Self-Adaptive PSR** · "
            f"Dynamic PSR {format_ratio(result.target_psr)}x · "
            f"적용 모델: {getattr(result, 'applied_model', 'PSR')} · "
            f"{result.valuation_note}"
        )
    elif result.company_type == "T" or result.valuation_model in ("Forward PER", "Adaptive PER"):
        peg_info = ""
        if getattr(result, "peg_ratio", None):
            peg_info = f" · PEG {result.peg_ratio:.2f} ({result.peg_verdict})"
        st.info(
            f"**{result.company_type_label}** · **Intelligent Forward PER** · "
            f"Target PER {format_ratio(result.target_per)}x{peg_info} · "
            f"{result.valuation_note}"
        )
    elif result.valuation_model == "Value PER" or result.company_type == "V":
        st.info(
            f"**{result.company_type_label}** · **Value PER** · "
            f"Target PER {format_ratio(result.target_per)}x (10~15x) · "
            f"{result.valuation_note}"
        )
    elif result.valuation_model == "PEG & Forward PER" or result.company_type == "B":
        st.info(
            f"**{result.company_type_label}** · **PEG & Forward PER** · "
            f"Forward PER {format_ratio(result.target_per)}x · {result.valuation_note}"
        )
    else:
        st.info(
            f"**투자의견: {result.rating}** · Target PER {format_ratio(result.target_per)}x "
            f"(현재 PER {format_ratio(result.current_per)})"
        )

    if result.analysis and result.analysis.consensus.available:
        st.success(
            f"**{result.analysis.consensus.surprise_label}** — "
            f"EPS 서프라이즈 {result.analysis.consensus.eps_surprise_pct:+.1f}%"
        )

    if not result.scenario_table.empty:
        st.markdown("#### Bull / Base / Bear 시나리오")
        fmt_map = {
            "매출성장률(%)": "{:.1f}",
            "Y+1 EPS": "{:,.2f}",
            "Y+1 목표주가": "{:,.2f}",
            "상승여력(%)": "{:+.1f}",
        }
        if "Target PSR" in result.scenario_table.columns:
            fmt_map["Target PSR"] = "{:.2f}"
        if "Target P/B" in result.scenario_table.columns:
            fmt_map["Target P/B"] = "{:.2f}"
        if "Target PER" in result.scenario_table.columns:
            fmt_map["Target PER"] = "{:.1f}"
        st.dataframe(
            result.scenario_table.style.format(fmt_map, na_rep="-"),
            use_container_width=True,
            key="forecast_scenario_table",
        )

    st.markdown("#### 추정치 요약표")
    st.dataframe(
        result.forecast_table.style.format(
            {
                "매출액": "{:,.0f}",
                "영업이익": "{:,.0f}",
                "이익률(%)": "{:.2f}",
                "예상 EPS": "{:,.2f}",
                "적정 예상 주가": "{:,.2f}",
                "현재가 대비 기대수익률(%)": "{:+.1f}",
            },
            na_rep="-",
        ),
        use_container_width=True,
        key="forecast_summary_table",
    )

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        bar6 = build_forecast_bar_chart(
            result.historical_chart_df,
            result.forecast_chart_df,
        )
        if bar6:
            st.plotly_chart(bar6, use_container_width=True, key="forecast_bar6")
    with col_chart2:
        if result.analysis:
            line_fig = build_scenario_chart(
                result.analysis.scenarios,
                result.current_price,
            )
        else:
            line_fig = build_target_price_chart(
                result.current_price,
                result.forecast_rows,
            )
        st.plotly_chart(line_fig, use_container_width=True, key="forecast_scenario_or_target")
        if result.analysis:
            a = result.analysis
            st.markdown(f"**업종** · {a.sector_profile.sector} / {a.sector_profile.industry}")
            st.markdown(f"**모델** · {a.sector_profile.description}")
            st.markdown(f"**비용 구조** · {a.cost_structure.summary}")
            st.markdown(f"**거시 민감도** · {a.macro.summary}")
            st.markdown(
                f"**PER Range** · High {a.per_high:.1f}x / Low {a.per_low:.1f}x / Mid {a.per_mid:.1f}x"
            )

    st.markdown("#### 정성적 분석 소견")
    for title, body in result.commentary.items():
        st.markdown(f"**[{title}]**")
        st.markdown(body)

    with st.expander("추정 모델 파라미터"):
        st.markdown(
            f"- 가중 매출 성장률: **{result.revenue_growth_pct:.2f}%** "
            f"(CAGR 40% + 직전년 YoY 60%)\n"
            f"- 3개년 평균 영업이익률: **{result.avg_op_margin_pct:.2f}%**\n"
            f"- 법인세율 가정: **20%** (당기순이익 = 영업이익 × 0.8)\n"
            f"- 발행주식수: **{result.shares_outstanding:,.0f}**"
        )


def main() -> None:
    inject_global_styles()
    st.markdown(
        '<p class="fin-section-title">주식 분석 대시보드</p>'
        '<p class="fin-section-caption">차트 · 재무제표 · 실적 전망 · 증권사 리포트</p>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("분석 설정")
        with st.form("analysis_form", clear_on_submit=False):
            ticker_input = st.text_input(
                "주식 티커",
                value=st.session_state.get("ticker_draft", ""),
                placeholder="예: AAPL, TSLA, 005930.KS",
                help="미국·한국 등 Yahoo Finance 지원 티커를 입력하세요.",
            )
            period_label = st.selectbox("분석 기간", list(PERIOD_OPTIONS.keys()))
            start = st.form_submit_button(
                "분석 시작", type="primary", use_container_width=True
            )

    if start:
        st.session_state.ticker_draft = ticker_input
        if not ticker_input.strip():
            st.warning("티커를 입력해 주세요.")
            st.stop()
        try:
            normalized = validate_ticker(ticker_input)
            st.session_state.analysis_ticker = normalized
            st.session_state.analysis_period_label = period_label
        except TickerNotFoundError:
            st.warning("올바른 티커를 입력해 주세요.")
            st.stop()

    ticker = st.session_state.analysis_ticker
    period_label = st.session_state.analysis_period_label

    if not ticker or not period_label:
        st.info("👈 사이드바에서 티커와 분석 기간을 선택한 뒤 **분석 시작**을 눌러 주세요.")
        st.stop()

    period = PERIOD_OPTIONS[period_label]

    try:
        price_df = fetch_price_history(ticker, period)
        fin_data = fetch_financial_statements(ticker)
        info = fetch_ticker_info(ticker)
        earnings_est = fetch_earnings_estimates(ticker)
        quarterly_fin = fetch_quarterly_financials(ticker)
    except TickerNotFoundError:
        st.warning("올바른 티커를 입력해 주세요.")
        st.stop()
    except Exception:
        st.error("데이터를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
        st.stop()

    currency = render_header(info, ticker)

    ma_df, rsi, macd_df, bb_df, crossovers = enrich_price_data(price_df)
    tech_summary = summarize_technical_indicators(price_df, rsi, macd_df, bb_df, crossovers)
    series = extract_annual_series(
        fin_data.get("financials"),
        fin_data.get("balance_sheet"),
        fin_data.get("cashflow"),
    )
    metrics_df = build_metrics_table(series)
    chart_df = compute_annual_amounts_chart(series)

    tab_chart, tab_fin, tab_forecast, tab_report = st.tabs(
        [
            "주가 및 기술적 차트",
            "재무제표 분석",
            "향후 3개년 실적 전망 및 추정 소견",
            "증권사 리포트",
        ]
    )

    forecast_result = run_financial_forecast(
        series,
        info,
        financials=fin_data.get("financials"),
        earnings_estimates=earnings_est,
        quarterly_financials=quarterly_fin,
    )

    with tab_chart:
        st.markdown(
            '<div class="fin-card" style="padding-bottom:8px;">'
            '<p class="fin-section-title">주가 및 기술적 지표</p>'
            '<p class="fin-section-caption">MA 20·60 · 볼린저 밴드 · 매물대 · RSI · MACD</p>'
            "</div>",
            unsafe_allow_html=True,
        )
        chart_col, insight_col = st.columns([4, 1], gap="medium")
        with chart_col:
            fig = build_price_chart(price_df, ma_df, rsi, macd_df, bb_df, crossovers)
            st.plotly_chart(fig, use_container_width=True, key="tab_price_chart")
        with insight_col:
            render_technical_signals_panel(tech_summary)

    with tab_fin:
        st.subheader("주요 재무 지표 (최근 4개년)")
        if metrics_df.empty:
            st.warning("재무제표 데이터를 가져올 수 없습니다.")
        else:
            st.dataframe(
                metrics_df.style.format("{:,.2f}", na_rep="-"),
                use_container_width=True,
                key="tab_fin_metrics_table",
            )
            st.caption(
                "부채비율 = 총부채÷자본, ROE = 당기순이익÷자본×100."
            )

        bar_fig = build_revenue_profit_bar(chart_df)
        if bar_fig:
            st.plotly_chart(bar_fig, use_container_width=True, key="tab_fin_revenue_bar")
        else:
            st.info("매출·영업이익 차트를 표시할 데이터가 없습니다.")

    with tab_forecast:
        render_forecast_tab(series, info, metrics_df, forecast_result, currency)

    with tab_report:
        render_research_report_tab(ticker, info, series, metrics_df, forecast_result)

    company_name = info.get("longName") or info.get("shortName") or ticker
    st.divider()
    st.caption(f"자료: {company_name}, 리서치센터 추정")
    st.caption(DISCLAIMER_KO)


if __name__ == "__main__":
    main()
