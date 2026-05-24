"""주식 분석 대시보드 — Streamlit 메인 앱."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="주식 분석 대시보드",
    page_icon="📈",
    layout="wide",
)

try:
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
        load_analysis_data,
        validate_ticker,
    )
    try:
        from data_loader import fetch_chart_price_history
    except ImportError:
        from data_loader import fetch_price_history as fetch_chart_price_history
    from financials import build_metrics_table, compute_annual_amounts_chart, extract_annual_series
    from forecasting import run_cached_financial_forecast
    from indicators import enrich_price_data, summarize_technical_indicators
    from research_report import build_research_report, render_report_html
    from report_pdf import generate_report_pdf
    from macro_dashboard import render_macro_dashboard
    from ui_components import (
        inject_global_styles,
        render_app_hero,
        render_card_open,
        render_card_close,
        render_chart_period_selector,
        render_kpi_row,
        render_no_ticker_notice,
        render_section_heading,
        render_stock_header_card,
        render_technical_signals_panel,
    )
except ImportError as exc:
    st.error(
        f"**모듈 import 오류:** `{exc}`\n\n"
        "GitHub 저장소의 Python 파일이 서로 다른 버전입니다. "
        "`upload_to_github` 폴더의 **모든 .py 파일**을 GitHub에 다시 올려 주세요."
    )
    st.stop()


if "analysis_ticker" not in st.session_state:
    st.session_state.analysis_ticker = None
if "analysis_period_label" not in st.session_state:
    st.session_state.analysis_period_label = None


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_report_pdf(ticker: str, period: str) -> bytes:
    """리포트 PDF — 버튼 클릭 시에만 생성·캐시."""
    from data_loader import load_analysis_data

    bundle = load_analysis_data(ticker, period)
    series = extract_annual_series(
        bundle["fin_data"].get("financials"),
        bundle["fin_data"].get("balance_sheet"),
        bundle["fin_data"].get("cashflow"),
    )
    forecast = run_cached_financial_forecast(ticker, period)
    if forecast is None:
        raise ValueError("추정 데이터 없음")
    report = build_research_report(ticker, bundle["info"], series, forecast)
    return generate_report_pdf(report)


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
    st.markdown('<div class="fin-report-shell">', unsafe_allow_html=True)
    render_section_heading("증권사 리포트")
    st.markdown(
        '<p class="fin-caption">LS증권 Earnings Review 형식 · 업종·컨센서스·시나리오 분석 통합</p>',
        unsafe_allow_html=True,
    )

    if forecast_result is None:
        st.warning("리포트 생성에 필요한 추정 데이터가 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    report = build_research_report(ticker, info, series, forecast_result)
    currency = resolve_currency(info, ticker)

    st.markdown(
        f'<p class="fin-caption">{getattr(forecast_result, "horizon_label", "12-Month Forward (1년 후 예상 실적)")}</p>',
        unsafe_allow_html=True,
    )

    upside_tone = "up" if report.upside_pct >= 0 else "down"
    kpi_items = [
        ("투자의견", report.rating_en.split()[0], None),
        ("12M Forward 목표주가", format_price(report.target_price, currency), None),
        ("현재주가", format_price(report.current_price, currency), None),
        ("상승여력", format_percent(report.upside_pct, signed=True), upside_tone),
    ]
    if forecast_result.analysis and forecast_result.analysis.consensus.available:
        surprise = forecast_result.analysis.consensus.eps_surprise_pct
        surprise_tone = "up" if surprise >= 0 else "down"
        kpi_items.append(
            ("어닝 서프라이즈", f"{surprise:+.1f}%", surprise_tone),
        )
    else:
        kpi_items.append(("컨센서스", "N/A", None))
    render_kpi_row(kpi_items)

    if forecast_result.analysis and forecast_result.analysis.consensus.available:
        st.info(f"📊 **{forecast_result.analysis.consensus.surprise_label}**")

    col_left, col_right = st.columns([2, 3], gap="large")

    with col_left:
        st.markdown('<div class="fin-report-panel">', unsafe_allow_html=True)
        render_section_heading("Stock Data & Metrics", level=4)
        for k, v in report.stock_data.items():
            st.markdown(f"**{k}** · {v}")

        if forecast_result.analysis:
            st.markdown(f"**업종 모델** · {forecast_result.analysis.sector_profile.model_type}")
            st.caption(forecast_result.analysis.sector_profile.description)

        render_section_heading("시나리오별 목표주가", level=4)
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
            render_section_heading("주요 재무 지표", level=4)
            st.dataframe(
                metrics_df.style.format("{:,.2f}", na_rep="-"),
                use_container_width=True,
                key="report_metrics_table",
            )

        if st.button("📄 PDF 생성", type="primary", use_container_width=True, key="report_pdf_prepare"):
            try:
                st.session_state.report_pdf_bytes = _cached_report_pdf(
                    ticker,
                    PERIOD_OPTIONS.get(st.session_state.analysis_period_label or "", "1y"),
                )
                st.session_state.report_pdf_ticker = ticker
            except Exception as exc:
                st.error(f"PDF 생성 오류: {exc}")

        pdf_bytes = (
            st.session_state.get("report_pdf_bytes")
            if st.session_state.get("report_pdf_ticker") == ticker
            else None
        )
        if pdf_bytes:
            st.download_button(
                label="PDF 다운로드",
                data=pdf_bytes,
                file_name=f"{ticker.replace('.', '_')}_research_report.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="report_pdf_download",
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown(
            '<div class="fin-report-panel fin-report-html-wrap">',
            unsafe_allow_html=True,
        )
        render_section_heading("Professional Analysis Report", level=4)
        st.markdown(render_report_html(report), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_forecast_tab(
    series: dict,
    info: dict,
    metrics_df,
    forecast_result=None,
    currency: str = "USD",
) -> None:
    """향후 3개년 실적 전망 및 추정 소견 탭."""
    render_section_heading("향후 3개년 실적 전망 및 추정 소견")
    st.markdown(
        '<p class="fin-caption">증권사 리서치 방식의 <strong>전통적 재무 추정 모델</strong> '
        "(CAGR·가중 성장률, 영업이익률 시나리오, Target PER)을 자동 적용합니다.</p>",
        unsafe_allow_html=True,
    )

    result = forecast_result
    if result is None:
        result = run_cached_financial_forecast(
            st.session_state.analysis_ticker or "",
            PERIOD_OPTIONS.get(st.session_state.analysis_period_label or "", "1y"),
        )

    if result is None:
        st.warning(
            "추정에 필요한 재무 데이터(매출·주가·발행주식수)가 부족합니다. "
            "다른 티커를 시도하거나 재무제표 탭에서 데이터 제공 여부를 확인해 주세요."
        )
        return

    upside_tone = "up" if result.upside_pct >= 0 else "down"
    render_kpi_row(
        [
            ("현재 주가", format_price(result.current_price, currency), None),
            ("12M Forward 목표주가", format_price(result.y1_target_price, currency), None),
            ("기대 수익률 (12M)", format_percent(result.upside_pct, signed=True), upside_tone),
        ]
    )

    st.markdown(
        f'<p class="fin-caption">{getattr(result, "horizon_label", "12-Month Forward (1년 후 예상 실적)")}</p>',
        unsafe_allow_html=True,
    )

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
        render_section_heading("Bull / Base / Bear 시나리오", level=4)
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

    render_section_heading("추정치 요약표", level=4)
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

    render_section_heading("정성적 분석 소견", level=4)
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


def render_financial_tab(
    series: dict,
    info: dict,
    metrics_df,
    chart_df,
    forecast_result,
    currency: str,
    ticker: str,
    period: str,
) -> None:
    """재무분석 — 재무제표 + 실적 전망 통합."""
    render_section_heading("재무 분석")
    st.markdown(
        '<p class="fin-caption">재무제표 · 실적 추정 · 목표주가를 한 화면에서 확인합니다.</p>',
        unsafe_allow_html=True,
    )

    render_card_open("주요 재무 지표 (최근 4개년)")
    if metrics_df.empty:
        st.warning("재무제표 데이터를 가져올 수 없습니다.")
    else:
        st.dataframe(
            metrics_df.style.format("{:,.2f}", na_rep="-"),
            use_container_width=True,
            key="tab_fin_metrics_table",
        )
        st.caption("부채비율 = 총부채÷자본, ROE = 당기순이익÷자본×100.")
    render_card_close()

    bar_fig = build_revenue_profit_bar(chart_df)
    if bar_fig:
        render_card_open("매출 · 영업이익 추이")
        st.plotly_chart(bar_fig, use_container_width=True, key="tab_fin_revenue_bar")
        render_card_close()

    st.divider()
    if forecast_result is None:
        with st.spinner("재무 추정·목표주가 계산 중..."):
            forecast_result = run_cached_financial_forecast(ticker, period)
    render_forecast_tab(series, info, metrics_df, forecast_result, currency)


def main() -> None:
    inject_global_styles()
    render_app_hero(
        "주식 분석 대시보드",
        "주가 · 재무 · 매크로 · 리포트",
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
            period_label = st.selectbox("재무 분석 기간", list(PERIOD_OPTIONS.keys()))
            start = st.form_submit_button(
                "분석 시작", type="primary", use_container_width=True
            )

    if start:
        st.session_state.ticker_draft = ticker_input
        if not ticker_input.strip():
            st.warning("티커를 입력해 주세요.")
        else:
            try:
                normalized = validate_ticker(ticker_input)
                st.session_state.analysis_ticker = normalized
                st.session_state.analysis_period_label = period_label
            except TickerNotFoundError:
                st.warning("올바른 티커를 입력해 주세요.")

    ticker = st.session_state.analysis_ticker
    period_label = st.session_state.analysis_period_label
    has_ticker = bool(ticker and period_label)

    tab_chart, tab_fin, tab_macro, tab_report = st.tabs(
        [
            "주가/기술적 지표",
            "재무분석",
            "매크로 지표",
            "증권사 리포트",
        ]
    )

    # 매크로 — 종목과 무관하게 항상 표시
    with tab_macro:
        render_macro_dashboard()

    if not has_ticker:
        with tab_chart:
            render_no_ticker_notice()
        with tab_fin:
            render_no_ticker_notice()
        with tab_report:
            render_no_ticker_notice()
        st.divider()
        st.caption(DISCLAIMER_KO)
        return

    period = PERIOD_OPTIONS[period_label]

    try:
        with st.spinner("시장 데이터 불러오는 중..."):
            bundle = load_analysis_data(ticker, period)
        price_df = bundle["price_df"]
        fin_data = bundle["fin_data"]
        info = bundle["info"]
    except TickerNotFoundError:
        st.warning("올바른 티커를 입력해 주세요.")
        return
    except Exception:
        st.error("데이터를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
        return

    currency = render_header(info, ticker)

    series = extract_annual_series(
        fin_data.get("financials"),
        fin_data.get("balance_sheet"),
        fin_data.get("cashflow"),
    )
    metrics_df = build_metrics_table(series)
    chart_df = compute_annual_amounts_chart(series)
    forecast_result = None

    with tab_chart:
        render_card_open("주가 · 기술적 지표")
        chart_period = render_chart_period_selector()
        try:
            chart_price_df = fetch_chart_price_history(ticker, chart_period)
        except TickerNotFoundError:
            chart_price_df = price_df

        ma_df, rsi, macd_df, bb_df, crossovers = enrich_price_data(chart_price_df)
        tech_summary = summarize_technical_indicators(
            chart_price_df, rsi, macd_df, bb_df, crossovers
        )
        chart_col, insight_col = st.columns([4, 1], gap="medium")
        with chart_col:
            fig = build_price_chart(
                chart_price_df, ma_df, rsi, macd_df, bb_df, crossovers
            )
            st.plotly_chart(fig, use_container_width=True, key="tab_price_chart")
        with insight_col:
            render_technical_signals_panel(tech_summary)
        render_card_close()

    with tab_fin:
        render_financial_tab(
            series, info, metrics_df, chart_df, forecast_result, currency, ticker, period
        )

    with tab_report:
        if forecast_result is None:
            with st.spinner("리포트 데이터 준비 중..."):
                forecast_result = run_cached_financial_forecast(ticker, period)
        render_research_report_tab(ticker, info, series, metrics_df, forecast_result)

    company_name = info.get("longName") or info.get("shortName") or ticker
    st.divider()
    st.caption(f"자료: {company_name}, 리서치센터 추정")
    st.caption(DISCLAIMER_KO)


if __name__ == "__main__":
    main()
