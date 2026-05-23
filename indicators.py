"""기술적 지표 계산."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import (
    BOLLINGER_PERIOD,
    BOLLINGER_STD,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    MA_WINDOWS,
    RSI_PERIOD,
)


@dataclass
class MaCrossover:
    """이동평균선 교차 이벤트."""

    date: pd.Timestamp
    kind: str
    label: str
    price: float


@dataclass
class TechnicalSummary:
    """RSI·MACD·MA 교차·볼린저 한글 해설 및 UI 상태."""

    rsi_text: str
    macd_text: str
    crossover_text: str
    bollinger_text: str
    latest_rsi: float | None
    latest_macd: float | None
    latest_signal: float | None
    rsi_label: str = "중립"
    rsi_tone: str = "yellow"
    macd_label: str = "중립"
    macd_tone: str = "yellow"
    ma_label: str = "중립"
    ma_tone: str = "yellow"
    bb_label: str = "중립"
    bb_tone: str = "yellow"


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """이동평균선(MA) 추가."""
    result = pd.DataFrame(index=df.index)
    close = df["Close"]
    for window in MA_WINDOWS:
        result[f"MA{window}"] = close.rolling(window=window, min_periods=1).mean()
    return result


def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Wilder RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_macd(
    close: pd.Series,
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> pd.DataFrame:
    """MACD, Signal, Histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {"MACD": macd_line, "Signal": signal_line, "Histogram": histogram},
        index=close.index,
    )


def compute_bollinger_bands(
    close: pd.Series,
    period: int = BOLLINGER_PERIOD,
    num_std: float = BOLLINGER_STD,
) -> pd.DataFrame:
    """볼린저 밴드 (중심선·상단·하단)."""
    mid = close.rolling(window=period, min_periods=1).mean()
    std = close.rolling(window=period, min_periods=1).std().fillna(0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    return pd.DataFrame({"Mid": mid, "Upper": upper, "Lower": lower}, index=close.index)


def compute_volume_profile(
    price_df: pd.DataFrame,
    bins: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    """가격대별 거래량(매물대) 히스토그램."""
    if price_df.empty:
        return np.array([]), np.array([])

    typical = (price_df["High"] + price_df["Low"] + price_df["Close"]) / 3
    low, high = float(typical.min()), float(typical.max())
    if low == high:
        return np.array([low]), np.array([float(price_df["Volume"].sum())])

    edges = np.linspace(low, high, bins + 1)
    volumes, edges = np.histogram(typical, bins=edges, weights=price_df["Volume"])
    centers = (edges[:-1] + edges[1:]) / 2
    return centers, volumes


def detect_ma_crossovers(
    price_df: pd.DataFrame,
    ma_df: pd.DataFrame,
    fast_col: str = "MA20",
    slow_col: str = "MA60",
) -> list[MaCrossover]:
    """MA20·MA60 골든/데드크로스 탐지."""
    if fast_col not in ma_df.columns or slow_col not in ma_df.columns:
        return []

    diff = ma_df[fast_col] - ma_df[slow_col]
    prev = diff.shift(1)
    events: list[MaCrossover] = []

    for idx in diff.index[1:]:
        d, p = diff.loc[idx], prev.loc[idx]
        if pd.isna(d) or pd.isna(p):
            continue
        price = float(price_df.loc[idx, "Close"])
        if p <= 0 < d:
            events.append(
                MaCrossover(
                    date=idx,
                    kind="golden",
                    label="골든크로스(Buy)",
                    price=price,
                )
            )
        elif p >= 0 > d:
            events.append(
                MaCrossover(
                    date=idx,
                    kind="death",
                    label="데드크로스(Sell)",
                    price=price,
                )
            )
    return events


def summarize_technical_indicators(
    price_df: pd.DataFrame,
    rsi: pd.Series,
    macd_df: pd.DataFrame,
    bb_df: pd.DataFrame,
    crossovers: list[MaCrossover],
) -> TechnicalSummary:
    """RSI·MACD·볼린저·MA 교차 상태를 한글 애널리스트 문체로 요약."""
    latest_rsi = float(rsi.iloc[-1]) if len(rsi) else None
    latest_macd = float(macd_df["MACD"].iloc[-1]) if len(macd_df) else None
    latest_signal = float(macd_df["Signal"].iloc[-1]) if len(macd_df) else None
    hist = float(macd_df["Histogram"].iloc[-1]) if len(macd_df) else 0.0

    if latest_rsi is None:
        rsi_text = "RSI 데이터가 부족하여 판단이 제한됨."
        rsi_label, rsi_tone = "데이터 부족", "yellow"
    elif latest_rsi >= 70:
        rsi_text = "과매수 구간 — 단기 조정 가능성에 유의가 요구됨."
        rsi_label, rsi_tone = "과매수", "red"
    elif latest_rsi <= 30:
        rsi_text = "과매도 구간 — 기술적 반등 여지가 열려 있음."
        rsi_label, rsi_tone = "과매도", "green"
    elif latest_rsi >= 55:
        rsi_text = "중립 상단 — 상승 모멘텀이 유지되는 것으로 판단됨."
        rsi_label, rsi_tone = "상승", "green"
    elif latest_rsi <= 45:
        rsi_text = "중립 하단 — 약세 압력이 잔존하는 것으로 평가됨."
        rsi_label, rsi_tone = "하락", "red"
    else:
        rsi_text = "중립 구간 — 뚜렷한 과매수·과매도 신호는 없음."
        rsi_label, rsi_tone = "중립", "yellow"

    if latest_macd is None or latest_signal is None:
        macd_text = "MACD 데이터가 부족하여 추세 판단이 제한됨."
        macd_label, macd_tone = "데이터 부족", "yellow"
    elif latest_macd > latest_signal and hist > 0:
        macd_text = "시그널선 상회 — 단기 상승 추세가 유지되는 것으로 판단됨."
        macd_label, macd_tone = "상승", "green"
    elif latest_macd < latest_signal and hist < 0:
        macd_text = "시그널선 하회 — 하락 추세가 우세한 것으로 평가됨."
        macd_label, macd_tone = "하락", "red"
    elif latest_macd > latest_signal:
        macd_text = "시그널선 상회 — 모멘텀 강도는 제한적으로 판단됨."
        macd_label, macd_tone = "약상승", "yellow"
    else:
        macd_text = "시그널선 하회 — 약세 신호가 우세한 것으로 평가됨."
        macd_label, macd_tone = "하락", "red"

    if crossovers:
        last = crossovers[-1]
        days_ago = (price_df.index[-1] - last.date).days
        if last.kind == "golden":
            ma_label, ma_tone = "골든크로스", "green"
            crossover_text = f"▲ MA20·60 골든크로스 ({days_ago}일 전) — 중기 상승 전환 신호."
        else:
            ma_label, ma_tone = "데드크로스", "red"
            crossover_text = f"▼ MA20·60 데드크로스 ({days_ago}일 전) — 중기 하락 전환 신호."
    else:
        ma_label, ma_tone = "추세 유지", "yellow"
        crossover_text = "MA20·60 교차 없음 — 기존 추세가 유지되는 것으로 판단됨."

    close = float(price_df["Close"].iloc[-1])
    upper = float(bb_df["Upper"].iloc[-1])
    lower = float(bb_df["Lower"].iloc[-1])
    mid = float(bb_df["Mid"].iloc[-1])
    if close >= upper:
        bb_label, bb_tone = "상단 돌파", "red"
        bollinger_text = "볼린저 상단 근접 — 변동성 확대·과열 구간으로 판단됨."
    elif close <= lower:
        bb_label, bb_tone = "하단 이탈", "green"
        bollinger_text = "볼린저 하단 근접 — 반등 가능성이 열려 있음."
    elif close > mid:
        bb_label, bb_tone = "중심 상회", "green"
        bollinger_text = "볼린저 중심 상회 — 완만한 상승 추세로 평가됨."
    else:
        bb_label, bb_tone = "중심 하회", "yellow"
        bollinger_text = "볼린저 중심 하회 — 조정 압력이 존재하는 것으로 판단됨."

    return TechnicalSummary(
        rsi_text=rsi_text,
        macd_text=macd_text,
        crossover_text=crossover_text,
        bollinger_text=bollinger_text,
        latest_rsi=latest_rsi,
        latest_macd=latest_macd,
        latest_signal=latest_signal,
        rsi_label=rsi_label,
        rsi_tone=rsi_tone,
        macd_label=macd_label,
        macd_tone=macd_tone,
        ma_label=ma_label,
        ma_tone=ma_tone,
        bb_label=bb_label,
        bb_tone=bb_tone,
    )


def enrich_price_data(
    price_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.DataFrame, list[MaCrossover]]:
    """차트용 지표 일괄 계산."""
    ma_df = add_moving_averages(price_df)
    rsi = compute_rsi(price_df["Close"])
    macd_df = compute_macd(price_df["Close"])
    bb_df = compute_bollinger_bands(price_df["Close"])
    crossovers = detect_ma_crossovers(price_df, ma_df)
    return ma_df, rsi, macd_df, bb_df, crossovers
