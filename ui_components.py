"""현대적 금융 앱 UI — 글로벌 CSS·카드·시그널 패널."""

from __future__ import annotations

import streamlit as st

from formatting import format_market_cap, format_percent, format_price, format_ratio, resolve_currency

_TONE = {
    "green": {"bg": "#ECFDF3", "border": "#12B76A", "text": "#027A48"},
    "red": {"bg": "#FEF3F2", "border": "#F04438", "text": "#B42318"},
    "yellow": {"bg": "#FFFAEB", "border": "#F79009", "text": "#B54708"},
}

GLOBAL_CSS = """
<style>
  .block-container { padding-top: 1.5rem; max-width: 1400px; }
  div[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #F5F7FA 0%, #EEF2F6 100%);
  }
  .fin-card {
    background: #FFFFFF;
    border: 1px solid #E4E7EC;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
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
