"""현대적 금융 앱 UI — 라이트 모드 전용 CSS·카드·시그널 패널."""

from __future__ import annotations

import streamlit as st

from formatting import format_market_cap, format_percent, format_price, format_ratio, resolve_currency

_TONE = {
    "green": {"bg": "#ECFDF3", "border": "#12B76A", "text": "#027A48"},
    "red": {"bg": "#FEF3F2", "border": "#F04438", "text": "#B42318"},
    "yellow": {"bg": "#FFFAEB", "border": "#F79009", "text": "#B54708"},
}
"""전문 금융 플랫폼 UI — 토스증권·인베스팅닷컴 스타일 (라이트 모드 고정)."""

from __future__ import annotations

import streamlit as st

from formatting import format_market_cap, format_percent, format_price, format_ratio, resolve_currency

# KR 시장 관행: 상승 Red · 하락 Blue
_UP = {"bg": "#FFEBEE", "border": "#FFCDD2", "text": "#E53935"}
_DOWN = {"bg": "#E3F2FD", "border": "#BBDEFB", "text": "#1565C0"}
_TONE = {
    "green": {"bg": "#E8F5E9", "border": "#A5D6A7", "text": "#2E7D32"},
    "red": _UP,
    "yellow": {"bg": "#FFF8E1", "border": "#FFE082", "text": "#F57F17"},
}

GLOBAL_CSS = """
<style>
  @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

  .stApp, .stApp[data-theme="dark"], .stApp[data-theme="light"] {
    color-scheme: light !important;
    --background-color: #F8F9FA;
    --secondary-background-color: #FFFFFF;
    --text-color: #191F28;
    --primary-color: #3182F6;
    font-family: 'Pretendard', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
  }
  [data-testid="stThemeSwitcher"] { display: none !important; }

  div[data-testid="stAppViewContainer"] { background: #F8F9FA !important; }
  section[data-testid="stSidebar"],
  section[data-testid="stSidebar"] > div {
    background: #FFFFFF !important;
    border-right: 1px solid #EEF1F4 !important;
  }
  section[data-testid="stSidebar"] .block-container { padding: 1.25rem 1rem !important; }
  section[data-testid="stSidebar"] h1 {
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    color: #191F28 !important;
    letter-spacing: -0.02em;
  }
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span { color: #4E5968 !important; }

  .main .block-container {
    padding-top: 1.25rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 1280px;
  }

  /* 탭 */
  .stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: transparent;
    border-bottom: 1px solid #EEF1F4;
  }
  .stTabs [data-baseweb="tab"] {
    height: 44px;
    padding: 0 18px;
    font-weight: 600;
    font-size: 0.88rem;
    color: #8B95A1;
    border-radius: 8px 8px 0 0;
  }
  .stTabs [aria-selected="true"] {
    color: #191F28 !important;
    background: #FFFFFF !important;
    border: 1px solid #EEF1F4 !important;
    border-bottom-color: #FFFFFF !important;
  }

  /* 타이포그래피 */
  .fin-hero { margin-bottom: 1.25rem; }
  .fin-hero-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: #191F28;
    letter-spacing: -0.03em;
    margin: 0 0 6px 0;
  }
  .fin-hero-sub {
    font-size: 0.9rem;
    color: #8B95A1;
    margin: 0;
    line-height: 1.5;
  }
  .fin-h3 {
    font-size: 1.05rem;
    font-weight: 700;
    color: #191F28;
    margin: 1.5rem 0 0.75rem 0;
    letter-spacing: -0.02em;
  }
  .fin-h4 {
    font-size: 0.92rem;
    font-weight: 700;
    color: #333D4B;
    margin: 1.25rem 0 0.5rem 0;
  }
  .fin-caption {
    font-size: 0.82rem;
    color: #8B95A1;
    line-height: 1.55;
    margin-bottom: 0.75rem;
  }

  /* 카드 */
  .fin-card {
    background: #FFFFFF;
    border: 1px solid #EEF1F4;
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    color: #191F28;
  }
  .fin-card-header {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #8B95A1;
    margin-bottom: 10px;
  }
  .fin-stock-name {
    font-size: 1.4rem;
    font-weight: 800;
    color: #191F28;
    letter-spacing: -0.03em;
    margin-bottom: 4px;
  }
  .fin-stock-ticker { font-size: 0.85rem; color: #8B95A1; margin-bottom: 20px; }

  .fin-kpi-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
  }
  @media (max-width: 1100px) { .fin-kpi-grid { grid-template-columns: repeat(3, 1fr); } }
  @media (max-width: 640px) { .fin-kpi-grid { grid-template-columns: repeat(2, 1fr); } }

  .fin-kpi-box {
    background: #F8F9FA;
    border: 1px solid #EEF1F4;
    border-radius: 12px;
    padding: 14px 16px;
    min-height: 72px;
  }
  .fin-kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: #8B95A1;
    margin-bottom: 6px;
  }
  .fin-kpi-value {
    font-size: 1.05rem;
    font-weight: 700;
    color: #191F28;
    line-height: 1.25;
    letter-spacing: -0.02em;
  }
  .fin-badge {
    display: inline-block;
    font-size: 0.82rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 8px;
    border: 1px solid transparent;
  }
  .fin-up { background: #FFEBEE; color: #E53935; border-color: #FFCDD2; }
  .fin-down { background: #E3F2FD; color: #1565C0; border-color: #BBDEFB; }
  .fin-neutral { background: #F2F4F6; color: #4E5968; border-color: #E5E8EB; }

  .fin-signals-title { font-size: 0.95rem; font-weight: 700; color: #191F28; margin-bottom: 12px; }
  .fin-signal-card {
    background: #F8F9FA;
    border: 1px solid #EEF1F4;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
  }
  .fin-signal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .fin-signal-name { font-size: 0.85rem; font-weight: 700; color: #333D4B; }
  .fin-signal-badge {
    font-size: 0.68rem; font-weight: 700; padding: 3px 10px;
    border-radius: 999px; letter-spacing: 0.02em;
  }
  .fin-signal-value { font-size: 1rem; font-weight: 700; color: #191F28; margin-bottom: 6px; }
  .fin-signal-summary { font-size: 0.76rem; color: #8B95A1; line-height: 1.5; }

  .fin-section-title { font-size: 1rem; font-weight: 700; color: #191F28; margin: 0 0 4px 0; }
  .fin-section-caption { font-size: 0.82rem; color: #8B95A1; margin-bottom: 12px; }

  /* 리포트 탭 레이아웃 */
  .fin-report-shell { padding: 4px 0 24px 0; }
  .fin-report-kpi-row { margin-bottom: 20px; }
  .fin-report-panel {
    background: #FFFFFF;
    border: 1px solid #EEF1F4;
    border-radius: 16px;
    padding: 20px 22px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    margin-bottom: 16px;
  }
  .fin-report-html-wrap { padding: 8px 4px 8px 8px; }

  /* Streamlit 표 · DataFrame */
  .stApp [data-testid="stMarkdownContainer"] p,
  .stApp [data-testid="stMarkdownContainer"] li,
  .stApp [data-testid="stCaptionContainer"],
  .stApp [data-testid="stCaptionContainer"] p,
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 { color: #191F28 !important; }

  .stApp [data-testid="stDataFrame"] td,
  .stApp [data-testid="stDataFrame"] th,
  .stApp [data-testid="stTable"] td,
  .stApp [data-testid="stTable"] th,
  .stApp .dataframe td,
  .stApp .dataframe th {
    color: #333D4B !important;
    background-color: #FFFFFF !important;
    border-color: #EEF1F4 !important;
    padding: 12px 14px !important;
    font-size: 0.84rem !important;
    line-height: 1.5 !important;
  }
  .stApp [data-testid="stDataFrame"] th,
  .stApp .dataframe thead th {
    background-color: #F2F4F6 !important;
    color: #191F28 !important;
    font-weight: 700 !important;
    font-size: 0.8rem !important;
  }
  .stApp [data-testid="stDataFrame"] tbody tr:nth-child(even) td,
  .stApp .dataframe tbody tr:nth-child(even) td {
    background-color: #FAFBFC !important;
  }

  /* Plotly 차트 카드 */
  div[data-testid="stPlotlyChart"] {
    background: #FFFFFF;
    border: 1px solid #EEF1F4;
    border-radius: 16px;
    padding: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
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
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_heading(title: str, *, level: int = 3) -> None:
    cls = "fin-h3" if level == 3 else "fin-h4"
    st.markdown(f'<p class="{cls}">{title}</p>', unsafe_allow_html=True)


def _change_badge_html(change) -> str:
    if change is None:
        return f'<span class="fin-badge fin-neutral">{format_percent(None, signed=True)}</span>'
    cls = "fin-up" if change >= 0 else "fin-down"
    return f'<span class="fin-badge {cls}">{format_percent(change, signed=True)}</span>'


def render_kpi_row(items: list[tuple[str, str, str | None]]) -> None:
    """KPI 카드 행 — (라벨, 값, up|down|None)."""
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
    """상단 종목 KPI 카드."""
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
  <div class="fin-card-header">Market Overview</div>
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
</div>
""",
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
</div>
"""


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
        _signal_card_html("볼린저 밴드", summary.bb_label, summary.bb_label, summary.bollinger_text, summary.bb_tone),
    ]
    st.markdown(
        f"""
<div class="fin-card fin-signals-wrap">
  <div class="fin-signals-title">기술적 시그널</div>
  {''.join(cards)}
</div>
""",
        unsafe_allow_html=True,
    )

GLOBAL_CSS = """
<style>
  /* 라이트 모드 고정 — 다크/시스템 설정 무시 */
  .stApp,
  .stApp[data-theme="dark"],
  .stApp[data-theme="light"] {
    color-scheme: light !important;
    --background-color: #F5F7FA;
    --secondary-background-color: #FFFFFF;
    --text-color: #101828;
    --primary-color: #003366;
  }
  [data-testid="stThemeSwitcher"] { display: none !important; }
  div[data-testid="stAppViewContainer"],
  section[data-testid="stSidebar"],
  section[data-testid="stSidebar"] > div {
    background: #F5F7FA !important;
  }
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span,
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3 {
    color: #101828 !important;
  }

  .block-container { padding-top: 1.5rem; max-width: 1400px; }

  .fin-card {
    background: #FFFFFF;
    border: 1px solid #E4E7EC;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
    color: #101828;
  }
  .fin-card-header {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #667085;
    margin-bottom: 12px;
  }
  .fin-stock-name {
    font-size: 1.35rem;
    font-weight: 700;
    color: #101828;
    margin-bottom: 4px;
  }
  .fin-stock-ticker {
    font-size: 0.85rem;
    color: #667085;
    margin-bottom: 18px;
  }
  .fin-metric-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 16px;
  }
  @media (max-width: 1100px) {
    .fin-metric-grid { grid-template-columns: repeat(3, 1fr); }
  }
  .fin-metric-item { min-width: 0; }
  .fin-metric-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: #667085;
    margin-bottom: 4px;
  }
  .fin-metric-value {
    font-size: 1.15rem;
    font-weight: 700;
    color: #101828;
    line-height: 1.3;
  }
  .fin-metric-value.positive { color: #12B76A; }
  .fin-metric-value.negative { color: #F04438; }
  .fin-signals-wrap { padding: 4px 0; }
  .fin-signals-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #101828;
    margin-bottom: 14px;
  }
  .fin-signal-card {
    background: #FAFBFC;
    border: 1px solid #E4E7EC;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
  }
  .fin-signal-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .fin-signal-name {
    font-size: 0.88rem;
    font-weight: 700;
    color: #101828;
  }
  .fin-signal-badge {
    font-size: 0.68rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 999px;
    letter-spacing: 0.02em;
  }
  .fin-signal-value {
    font-size: 1.05rem;
    font-weight: 600;
    color: #344054;
    margin-bottom: 6px;
  }
  .fin-signal-summary {
    font-size: 0.78rem;
    color: #667085;
    line-height: 1.45;
  }
  .fin-section-title {
    font-size: 1rem;
    font-weight: 700;
    color: #101828;
    margin: 0 0 4px 0;
  }
  .fin-section-caption {
    font-size: 0.8rem;
    color: #667085;
    margin-bottom: 12px;
  }

  /* Streamlit 기본 UI — 라이트 고정 */
  .stApp [data-testid="stMarkdownContainer"] p,
  .stApp [data-testid="stMarkdownContainer"] li,
  .stApp [data-testid="stCaptionContainer"],
  .stApp [data-testid="stCaptionContainer"] p,
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {
    color: #101828 !important;
  }
  .stApp [data-testid="stDataFrame"] td,
  .stApp [data-testid="stDataFrame"] th,
  .stApp [data-testid="stTable"] td,
  .stApp [data-testid="stTable"] th,
  .stApp .dataframe td,
  .stApp .dataframe th {
    color: #101828 !important;
    background-color: #FFFFFF !important;
    border-color: #E4E7EC !important;
  }
  .stApp [data-testid="stDataFrame"] th,
  .stApp .dataframe thead th {
    background-color: #F5F7FA !important;
    color: #101828 !important;
  }
</style>
"""


def inject_global_styles() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_stock_header_card(info: dict, ticker: str) -> str:
    """상단 종목 정보 카드. 통화 문자열 반환."""
    currency = resolve_currency(info, ticker)
    name = info.get("longName") or info.get("shortName") or ticker
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    change = info.get("regularMarketChangePercent")
    per = info.get("trailingPE") or info.get("forwardPE")
    pbr = info.get("priceToBook")
    ev_ebitda = info.get("enterpriseToEbitda")

    change_cls = ""
    if change is not None:
        change_cls = "positive" if change >= 0 else "negative"

    st.markdown(
        f"""
<div class="fin-card">
  <div class="fin-card-header">Market Overview</div>
  <div class="fin-stock-name">{name}</div>
  <div class="fin-stock-ticker">{ticker} · {currency}</div>
  <div class="fin-metric-grid">
    <div class="fin-metric-item">
      <div class="fin-metric-label">현재가</div>
      <div class="fin-metric-value">{format_price(price, currency)}</div>
    </div>
    <div class="fin-metric-item">
      <div class="fin-metric-label">등락률</div>
      <div class="fin-metric-value {change_cls}">{format_percent(change, signed=True)}</div>
    </div>
    <div class="fin-metric-item">
      <div class="fin-metric-label">시가총액</div>
      <div class="fin-metric-value">{format_market_cap(info.get("marketCap"), currency)}</div>
    </div>
    <div class="fin-metric-item">
      <div class="fin-metric-label">PER</div>
      <div class="fin-metric-value">{format_ratio(per, prefix="PER ")}</div>
    </div>
    <div class="fin-metric-item">
      <div class="fin-metric-label">PBR</div>
      <div class="fin-metric-value">{format_ratio(pbr, prefix="PBR ")}</div>
    </div>
    <div class="fin-metric-item">
      <div class="fin-metric-label">EV/EBITDA</div>
      <div class="fin-metric-value">{format_ratio(ev_ebitda, prefix="", suffix="x") if ev_ebitda else "N/A"}</div>
    </div>
  </div>
</div>
""",
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
</div>
"""


def render_technical_signals_panel(summary) -> None:
    """기술적 시그널 카드 컨테이너."""
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
        _signal_card_html("볼린저 밴드", summary.bb_label, summary.bb_label, summary.bollinger_text, summary.bb_tone),
    ]
    body = "".join(cards)
    st.markdown(
        f"""
<div class="fin-card fin-signals-wrap">
  <div class="fin-signals-title">기술적 시그널</div>
  {body}
</div>
""",
        unsafe_allow_html=True,
    )
