"""초이스스탁 스타일 UI — 라이트 모드 고정, 카드 기반 레이아웃."""

from __future__ import annotations

import streamlit as st

from config import CHART_PERIOD_OPTIONS
from formatting import format_market_cap, format_percent, format_price, format_ratio, resolve_currency

# KR 시장: 상승 Red · 하락 Blue
_UP = {"bg": "#FFF0F0", "border": "#FFCDD2", "text": "#E42828"}
_DOWN = {"bg": "#F0F6FF", "border": "#BBDEFB", "text": "#1565C0"}
_TONE = {
    "green": {"bg": "#F0FAF0", "border": "#C8E6C9", "text": "#2E7D32"},
    "red": _UP,
    "yellow": {"bg": "#FFFBE6", "border": "#FFE082", "text": "#F57F17"},
}

GLOBAL_CSS = """
<style>
  @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

  .stApp, .stApp[data-theme="dark"], .stApp[data-theme="light"] {
    color-scheme: light !important;
    --background-color: #FFFFFF;
    --secondary-background-color: #FFFFFF;
    --text-color: #111111;
    --primary-color: #E42828;
    font-family: 'Pretendard', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
  }
  [data-testid="stThemeSwitcher"] { display: none !important; }

  div[data-testid="stAppViewContainer"] { background: #FFFFFF !important; }
  section[data-testid="stSidebar"],
  section[data-testid="stSidebar"] > div {
    background: #FFFFFF !important;
    border-right: 1px solid #EDEDED !important;
  }
  section[data-testid="stSidebar"] .block-container { padding: 1.25rem 1rem !important; }

  .main .block-container {
    padding-top: 1rem;
    padding-left: 1.75rem;
    padding-right: 1.75rem;
    max-width: 1200px;
  }

  /* 탭 — 초이스스탁 스타일 */
  .stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: #FFFFFF;
    border-bottom: 2px solid #EDEDED;
  }
  .stTabs [data-baseweb="tab"] {
    height: 48px;
    padding: 0 20px;
    font-weight: 600;
    font-size: 0.9rem;
    color: #888888;
    background: transparent;
    border: none;
    border-radius: 0;
  }
  .stTabs [aria-selected="true"] {
    color: #111111 !important;
    background: #FFFFFF !important;
    border-bottom: 2px solid #E42828 !important;
    font-weight: 700 !important;
  }

  .fin-hero { margin-bottom: 1rem; }
  .fin-hero-title {
    font-size: 1.6rem;
    font-weight: 800;
    color: #111111;
    letter-spacing: -0.03em;
    margin: 0 0 4px 0;
  }
  .fin-hero-sub { font-size: 0.88rem; color: #888888; margin: 0; line-height: 1.5; }

  .fin-h3 {
    font-size: 1.1rem;
    font-weight: 700;
    color: #111111;
    margin: 1.25rem 0 0.5rem 0;
    letter-spacing: -0.02em;
  }
  .fin-h4 {
    font-size: 0.95rem;
    font-weight: 700;
    color: #333333;
    margin: 1rem 0 0.4rem 0;
  }
  .fin-caption { font-size: 0.8rem; color: #888888; line-height: 1.5; margin-bottom: 0.5rem; }

  .fin-card {
    background: #FFFFFF;
    border: 1px solid #EDEDED;
    border-radius: 12px;
    padding: 20px 22px;
    margin-bottom: 14px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    color: #111111;
  }
  .fin-card-compact { padding: 14px 16px; }
  .fin-card-title {
    font-size: 0.88rem;
    font-weight: 700;
    color: #111111;
    margin: 0 0 12px 0;
    letter-spacing: -0.01em;
  }
  .fin-card-header {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #AAAAAA;
    margin-bottom: 8px;
  }
  .fin-stock-name {
    font-size: 1.35rem;
    font-weight: 800;
    color: #111111;
    letter-spacing: -0.03em;
    margin-bottom: 2px;
  }
  .fin-stock-ticker { font-size: 0.82rem; color: #888888; margin-bottom: 16px; }

  .fin-kpi-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 10px;
  }
  @media (max-width: 1100px) { .fin-kpi-grid { grid-template-columns: repeat(3, 1fr); } }
  @media (max-width: 640px) { .fin-kpi-grid { grid-template-columns: repeat(2, 1fr); } }

  .fin-kpi-box {
    background: #FAFAFA;
    border: 1px solid #EDEDED;
    border-radius: 10px;
    padding: 12px 14px;
    min-height: 68px;
  }
  .fin-kpi-label { font-size: 0.7rem; font-weight: 600; color: #888888; margin-bottom: 4px; }
  .fin-kpi-value {
    font-size: 1rem;
    font-weight: 700;
    color: #111111;
    line-height: 1.25;
    letter-spacing: -0.02em;
  }
  .fin-badge {
    display: inline-block;
    font-size: 0.82rem;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid transparent;
  }
  .fin-up { background: #FFF0F0; color: #E42828; border-color: #FFCDD2; }
  .fin-down { background: #F0F6FF; color: #1565C0; border-color: #BBDEFB; }
  .fin-neutral { background: #F5F5F5; color: #666666; border-color: #E0E0E0; }

  .fin-period-wrap { margin-bottom: 12px; }
  .fin-period-label { font-size: 0.78rem; font-weight: 600; color: #888888; margin-bottom: 6px; }

  .fin-signals-title { font-size: 0.92rem; font-weight: 700; color: #111111; margin-bottom: 10px; }
  .fin-signal-card {
    background: #FAFAFA;
    border: 1px solid #EDEDED;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
  }
  .fin-signal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
  .fin-signal-name { font-size: 0.82rem; font-weight: 700; color: #333333; }
  .fin-signal-badge {
    font-size: 0.65rem; font-weight: 700; padding: 2px 8px;
    border-radius: 999px;
  }
  .fin-signal-value { font-size: 0.95rem; font-weight: 700; color: #111111; margin-bottom: 4px; }
  .fin-signal-summary { font-size: 0.74rem; color: #888888; line-height: 1.45; }

  .fin-report-shell { padding: 4px 0 20px 0; }
  .fin-report-kpi-row { margin-bottom: 16px; }
  .fin-report-panel {
    background: #FFFFFF;
    border: 1px solid #EDEDED;
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    margin-bottom: 14px;
  }
  .fin-report-html-wrap { padding: 4px 2px 4px 6px; }

  div[data-testid="stPlotlyChart"] {
    background: #FFFFFF;
    border: 1px solid #EDEDED;
    border-radius: 12px;
    padding: 4px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  }

  .stApp [data-testid="stDataFrame"] td,
  .stApp [data-testid="stDataFrame"] th,
  .stApp .dataframe td,
  .stApp .dataframe th {
    color: #333333 !important;
    background-color: #FFFFFF !important;
    border-color: #EDEDED !important;
    padding: 11px 12px !important;
    font-size: 0.84rem !important;
    line-height: 1.45 !important;
  }
  .stApp [data-testid="stDataFrame"] th,
  .stApp .dataframe thead th {
    background-color: #FAFAFA !important;
    color: #111111 !important;
    font-weight: 700 !important;
  }
</style>
"""


def inject_global_styles() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_app_hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
<div class="fin-hero">
  <p class="fin-hero-title">{title}</p>
  <p class="fin-hero-sub">{subtitle}</p>
</div>""",
        unsafe_allow_html=True,
    )


def render_section_heading(title: str, *, level: int = 3) -> None:
    cls = "fin-h3" if level == 3 else "fin-h4"
    st.markdown(f'<p class="{cls}">{title}</p>', unsafe_allow_html=True)


def render_card_open(title: str, *, compact: bool = False) -> None:
    cls = "fin-card fin-card-compact" if compact else "fin-card"
    st.markdown(f'<div class="{cls}"><p class="fin-card-title">{title}</p>', unsafe_allow_html=True)


def render_card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_chart_period_selector(key: str = "chart_period_label") -> str:
    """차트 기간 선택 — yfinance period 코드 반환."""
    labels = list(CHART_PERIOD_OPTIONS.keys())
    if key not in st.session_state:
        st.session_state[key] = "1년"
    st.markdown('<div class="fin-period-wrap">', unsafe_allow_html=True)
    st.markdown('<p class="fin-period-label">차트 기간</p>', unsafe_allow_html=True)
    selected = st.radio(
        "차트 기간",
        labels,
        index=labels.index(st.session_state[key]),
        horizontal=True,
        label_visibility="collapsed",
        key=f"{key}_radio",
    )
    st.session_state[key] = selected
    st.markdown("</div>", unsafe_allow_html=True)
    return CHART_PERIOD_OPTIONS[selected]


def _change_badge_html(change) -> str:
    if change is None:
        return f'<span class="fin-badge fin-neutral">{format_percent(None, signed=True)}</span>'
    cls = "fin-up" if change >= 0 else "fin-down"
    return f'<span class="fin-badge {cls}">{format_percent(change, signed=True)}</span>'


def render_kpi_row(items: list[tuple[str, str, str | None]]) -> None:
    cells = []
    for label, value, tone in items:
        if tone == "up":
            val_html = f'<span class="fin-badge fin-up">{value}</span>'
        elif tone == "down":
            val_html = f'<span class="fin-badge fin-down">{value}</span>'
        else:
            val_html = f'<span class="fin-kpi-value">{value}</span>'
        cells.append(
            f"""
<div class="fin-kpi-box">
  <div class="fin-kpi-label">{label}</div>
  {val_html}
</div>"""
        )
    st.markdown(
        f'<div class="fin-kpi-grid fin-report-kpi-row">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def render_stock_header_card(info: dict, ticker: str) -> str:
    currency = resolve_currency(info, ticker)
    name = info.get("longName") or info.get("shortName") or ticker
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    change = info.get("regularMarketChangePercent")
    per = info.get("trailingPE") or info.get("forwardPE")
    pbr = info.get("priceToBook")
    ev_ebitda = info.get("enterpriseToEbitda")
    change_html = _change_badge_html(change)

    st.markdown(
        f"""
<div class="fin-card">
  <div class="fin-card-header">종목 개요</div>
  <div class="fin-stock-name">{name}</div>
  <div class="fin-stock-ticker">{ticker} · {currency}</div>
  <div class="fin-kpi-grid">
    <div class="fin-kpi-box">
      <div class="fin-kpi-label">현재가</div>
      <div class="fin-kpi-value">{format_price(price, currency)}</div>
    </div>
    <div class="fin-kpi-box">
      <div class="fin-kpi-label">등락률</div>
      {change_html}
    </div>
    <div class="fin-kpi-box">
      <div class="fin-kpi-label">시가총액</div>
      <div class="fin-kpi-value">{format_market_cap(info.get("marketCap"), currency)}</div>
    </div>
    <div class="fin-kpi-box">
      <div class="fin-kpi-label">PER</div>
      <div class="fin-kpi-value">{format_ratio(per, prefix="")}x</div>
    </div>
    <div class="fin-kpi-box">
      <div class="fin-kpi-label">PBR</div>
      <div class="fin-kpi-value">{format_ratio(pbr, prefix="")}x</div>
    </div>
    <div class="fin-kpi-box">
      <div class="fin-kpi-label">EV/EBITDA</div>
      <div class="fin-kpi-value">{format_ratio(ev_ebitda, prefix="", suffix="x") if ev_ebitda else "N/A"}</div>
    </div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )
    return currency


def _signal_card_html(title: str, value: str, label: str, summary: str, tone: str) -> str:
    colors = _TONE.get(tone, _TONE["yellow"])
    return f"""
<div class="fin-signal-card">
  <div class="fin-signal-head">
    <span class="fin-signal-name">{title}</span>
    <span class="fin-signal-badge" style="background:{colors['bg']}; color:{colors['text']};
    border:1px solid {colors['border']};">{label}</span>
  </div>
  <div class="fin-signal-value">{value}</div>
  <div class="fin-signal-summary">{summary}</div>
</div>"""


def render_technical_signals_panel(summary) -> None:
    rsi_val = f"{summary.latest_rsi:.2f}" if summary.latest_rsi is not None else "N/A"
    macd_val = (
        f"{summary.latest_macd:.2f} / {summary.latest_signal:.2f}"
        if summary.latest_macd is not None and summary.latest_signal is not None
        else "N/A"
    )
    cards = [
        _signal_card_html("RSI", rsi_val, summary.rsi_label, summary.rsi_text, summary.rsi_tone),
        _signal_card_html("MACD", macd_val, summary.macd_label, summary.macd_text, summary.macd_tone),
        _signal_card_html("이동평균", summary.ma_label, summary.ma_label, summary.crossover_text, summary.ma_tone),
        _signal_card_html("볼린저", summary.bb_label, summary.bb_label, summary.bollinger_text, summary.bb_tone),
    ]
    st.markdown(
        f"""
<div class="fin-card fin-signals-wrap">
  <div class="fin-signals-title">기술적 시그널</div>
  {''.join(cards)}
</div>""",
        unsafe_allow_html=True,
    )


def render_no_ticker_notice() -> None:
    st.info("👈 사이드바에서 티커를 입력하고 **분석 시작**을 눌러 주세요.")
