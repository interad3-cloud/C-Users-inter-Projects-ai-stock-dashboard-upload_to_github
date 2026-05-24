"""글로벌 매크로 지표 수집 — 종목 분석과 독립 실행."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import yfinance as yf

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1&format=json"
TREASURY_TICKER = "^TNX"
VIX_TICKER = "^VIX"


@dataclass
class FearGreedReading:
    value: int
    label: str
    timestamp: str


@dataclass
class MacroIndicator:
    name: str
    value: str
    delta: str | None = None
    delta_tone: str | None = None  # up | down | None
    subtitle: str = ""


@dataclass
class MacroSnapshot:
    fear_greed: FearGreedReading | None = None
    treasury_rate: float | None = None
    treasury_change_bps: float | None = None
    treasury_history: pd.DataFrame = field(default_factory=pd.DataFrame)
    indicators: list[MacroIndicator] = field(default_factory=list)
    fetched_at: str = ""
    errors: list[str] = field(default_factory=list)


def _fetch_fred_series(series_id: str, *, tail: int = 24) -> pd.Series | None:
    """FRED 공개 CSV — API 키 없이 최신 시계열."""
    try:
        url = FRED_CSV.format(series_id=series_id)
        df = pd.read_csv(url)
        if df.empty or len(df.columns) < 2:
            return None
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().sort_values("date")
        if df.empty:
            return None
        return df.set_index("date")["value"].tail(tail)
    except Exception:
        return None


def _latest_pair(series: pd.Series | None) -> tuple[float | None, float | None]:
    if series is None or series.empty:
        return None, None
    latest = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else latest
    return latest, prev


def _fetch_fear_greed() -> FearGreedReading | None:
    try:
        with urllib.request.urlopen(FEAR_GREED_URL, timeout=8) as resp:
            payload = json.loads(resp.read().decode())
        item = payload.get("data", [{}])[0]
        return FearGreedReading(
            value=int(item.get("value", 0)),
            label=str(item.get("value_classification", "N/A")),
            timestamp=str(item.get("timestamp", "")),
        )
    except Exception:
        return None


def _fetch_treasury_history(period: str = "1y") -> pd.DataFrame:
    try:
        df = yf.Ticker(TREASURY_TICKER).history(period=period, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        out = df[["Close"]].copy()
        out.index = pd.to_datetime(out.index)
        out.columns = ["rate"]
        return out
    except Exception:
        return pd.DataFrame()


def _fetch_yf_last(ticker: str) -> tuple[float | None, float | None]:
    try:
        df = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
        if df is None or df.empty:
            return None, None
        close = df["Close"]
        latest = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) > 1 else latest
        return latest, prev
    except Exception:
        return None, None


def _format_delta(current: float | None, previous: float | None, *, unit: str = "", decimals: int = 2) -> tuple[str | None, str | None]:
    if current is None or previous is None:
        return None, None
    diff = current - previous
    if abs(diff) < 1e-9:
        return "0.00" + unit, None
    tone = "up" if diff > 0 else "down"
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:.{decimals}f}{unit}", tone


@st.cache_data(ttl=1800, show_spinner=False)
def load_macro_snapshot() -> MacroSnapshot:
    """매크로 대시보드용 스냅샷 — 30분 캐시."""
    errors: list[str] = []
    snapshot = MacroSnapshot(
        fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    snapshot.fear_greed = _fetch_fear_greed()
    if snapshot.fear_greed is None:
        errors.append("공포/탐욕 지수")

    treasury_hist = _fetch_treasury_history("1y")
    snapshot.treasury_history = treasury_hist
    if not treasury_hist.empty:
        snapshot.treasury_rate = float(treasury_hist["rate"].iloc[-1])
        if len(treasury_hist) > 1:
            prev = float(treasury_hist["rate"].iloc[-2])
            snapshot.treasury_change_bps = (snapshot.treasury_rate - prev) * 100
    else:
        errors.append("10년물 국채 금리")

    unrate = _fetch_fred_series("UNRATE", tail=6)
    un_latest, un_prev = _latest_pair(unrate)
    un_delta, un_tone = _format_delta(un_latest, un_prev, unit="%p", decimals=1)
    snapshot.indicators.append(
        MacroIndicator(
            name="미국 실업률",
            value=f"{un_latest:.1f}%" if un_latest is not None else "N/A",
            delta=un_delta,
            delta_tone=un_tone,
            subtitle="FRED · UNRATE",
        )
    )

    mich = _fetch_fred_series("MICH", tail=6)
    inf_latest, inf_prev = _latest_pair(mich)
    if inf_latest is None:
        t5y = _fetch_fred_series("T5YIE", tail=6)
        inf_latest, inf_prev = _latest_pair(t5y)
        inf_sub = "FRED · T5YIE (5Y Breakeven)"
    else:
        inf_sub = "FRED · MICH (소비자 기대)"
    inf_delta, inf_tone = _format_delta(inf_latest, inf_prev, unit="%p", decimals=1)
    snapshot.indicators.append(
        MacroIndicator(
            name="인플레이션 기대",
            value=f"{inf_latest:.1f}%" if inf_latest is not None else "N/A",
            delta=inf_delta,
            delta_tone=inf_tone,
            subtitle=inf_sub,
        )
    )

    vix, vix_prev = _fetch_yf_last(VIX_TICKER)
    vix_delta, vix_tone = _format_delta(vix, vix_prev, unit="", decimals=2)
    snapshot.indicators.append(
        MacroIndicator(
            name="VIX (변동성)",
            value=f"{vix:.2f}" if vix is not None else "N/A",
            delta=vix_delta,
            delta_tone=vix_tone,
            subtitle="yfinance · ^VIX",
        )
    )

    dxy, dxy_prev = _fetch_yf_last("DX-Y.NYB")
    dxy_delta, dxy_tone = _format_delta(dxy, dxy_prev, unit="", decimals=2)
    snapshot.indicators.append(
        MacroIndicator(
            name="달러 인덱스",
            value=f"{dxy:.2f}" if dxy is not None else "N/A",
            delta=dxy_delta,
            delta_tone=dxy_tone,
            subtitle="yfinance · DXY",
        )
    )

    snapshot.errors = errors
    return snapshot
