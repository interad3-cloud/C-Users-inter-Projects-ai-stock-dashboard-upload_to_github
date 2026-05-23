"""yfinance 데이터 수집 및 티커 검증."""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st
import yfinance as yf


class TickerNotFoundError(Exception):
    """유효하지 않은 티커."""


def normalize_ticker(ticker: str) -> str:
    """티커 문자열 정규화."""
    cleaned = re.sub(r"\s+", "", ticker.strip())
    if not cleaned:
        raise TickerNotFoundError("empty")
    # 한국 거래소 등 소문자 접미사 보존 (예: .ks)
    parts = cleaned.split(".")
    if len(parts) > 1:
        return f"{parts[0].upper()}.{'.'.join(p.lower() for p in parts[1:])}"
    return cleaned.upper()


def validate_ticker(ticker: str) -> str:
    """티커 유효성 검사 후 정규화된 티커 반환."""
    try:
        normalized = normalize_ticker(ticker)
    except TickerNotFoundError as exc:
        raise TickerNotFoundError("invalid") from exc

    try:
        hist = yf.Ticker(normalized).history(period="5d", auto_adjust=False)
        if hist is None or hist.empty:
            raise TickerNotFoundError("no_data")
    except TickerNotFoundError:
        raise
    except Exception as exc:
        raise TickerNotFoundError("fetch_error") from exc

    return normalized


@st.cache_data(ttl=3600, show_spinner=False)
def load_analysis_data(ticker: str, period: str) -> dict:
    """
    yfinance 호출을 1회 Ticker 객체로 통합 — Cloud에서 API 왕복 횟수 최소화.
    """
    stock = yf.Ticker(ticker)
    price_df = stock.history(period=period, auto_adjust=False)
    if price_df is None or price_df.empty:
        raise TickerNotFoundError("no_history")
    price_df = price_df.copy()
    price_df.index = pd.to_datetime(price_df.index)
    required = ["Open", "High", "Low", "Close", "Volume"]
    for col in required:
        if col not in price_df.columns:
            raise TickerNotFoundError("missing_columns")
    price_df = price_df[required]

    info = stock.info or {}
    if not info:
        info = {"symbol": ticker}
    else:
        info = dict(info)

    try:
        earnings_est = _safe_df(stock.earnings_estimate)
    except Exception:
        earnings_est = None

    quarterly_fin = _safe_df(stock.quarterly_financials)

    return {
        "price_df": price_df,
        "fin_data": {
            "financials": _safe_df(stock.financials),
            "balance_sheet": _safe_df(stock.balance_sheet),
            "cashflow": _safe_df(stock.cashflow),
        },
        "info": info,
        "earnings_est": earnings_est,
        "quarterly_fin": quarterly_fin,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price_history(ticker: str, period: str) -> pd.DataFrame:
    """일별 OHLCV 주가 데이터."""
    return load_analysis_data(ticker, period)["price_df"]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_earnings_estimates(ticker: str) -> pd.DataFrame | None:
    """분석가 컨센서스 (earnings_estimates)."""
    return load_analysis_data(ticker, "1y")["earnings_est"]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_quarterly_financials(ticker: str) -> pd.DataFrame | None:
    """분기 손익계산서."""
    return load_analysis_data(ticker, "1y")["quarterly_fin"]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_financial_statements(ticker: str) -> dict[str, pd.DataFrame | None]:
    """손익계산서, 재무상태표, 현금흐름표."""
    return load_analysis_data(ticker, "1y")["fin_data"]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ticker_info(ticker: str) -> dict:
    """종목 기본 정보 및 밸류에이션 지표."""
    return load_analysis_data(ticker, "1y")["info"]


def _safe_df(data) -> pd.DataFrame | None:
    if data is None:
        return None
    if isinstance(data, pd.DataFrame) and not data.empty:
        return data.copy()
    return None


def build_price_summary(price_df: pd.DataFrame) -> dict:
    """AI 프롬프트용 주가 요약."""
    close = price_df["Close"]
    latest = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else latest
    change_pct = ((latest - prev) / prev * 100) if prev else 0.0
    return {
        "최근 종가": round(latest, 2),
        "전일 대비(%)": round(change_pct, 2),
        "기간 최고가": round(float(close.max()), 2),
        "기간 최저가": round(float(close.min()), 2),
        "평균 거래량": int(price_df["Volume"].tail(20).mean()),
    }
