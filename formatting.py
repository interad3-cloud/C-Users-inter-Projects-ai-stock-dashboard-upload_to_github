"""금융 수치 포맷팅 — 통화·시가총액·배수."""

from __future__ import annotations


def resolve_currency(info: dict, ticker: str) -> str:
    """yfinance info 기준 표시 통화."""
    cur = (info.get("currency") or "").upper()
    if ticker.upper().endswith((".KS", ".KQ")) or cur == "KRW":
        return "KRW"
    if cur in ("", "USD"):
        return "USD"
    return cur


def format_price(value, currency: str = "USD") -> str:
    """현재가 등 — 소수 둘째 자리 + 통화."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.2f} {currency}"
    except (TypeError, ValueError):
        return "N/A"


def format_market_cap(value, currency: str = "USD") -> str:
    """글로벌 T / B / M 단위, 소수 둘째 자리."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"

    if v >= 1e12:
        return f"{v / 1e12:.2f}T {currency}"
    if v >= 1e9:
        return f"{v / 1e9:.2f}B {currency}"
    if v >= 1e6:
        return f"{v / 1e6:.2f}M {currency}"
    return f"{v:,.2f} {currency}"


def format_ratio(value, prefix: str = "", suffix: str = "") -> str:
    """PER, PBR 등 — 소수 둘째 자리."""
    if value is None:
        return "N/A"
    try:
        num = f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "N/A"
    return f"{prefix}{num}{suffix}" if prefix or suffix else num


def format_percent(value, signed: bool = False) -> str:
    """등락률 등 — 소수 둘째 자리 %."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
        if signed:
            return f"{v:+.2f}%"
        return f"{v:.2f}%"
    except (TypeError, ValueError):
        return "N/A"
