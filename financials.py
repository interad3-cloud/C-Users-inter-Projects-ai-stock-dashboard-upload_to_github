"""재무제표 정제 및 지표 계산."""

from __future__ import annotations

import pandas as pd

from config import FINANCIAL_ROW_KEYS, METRIC_LABELS_KO


def _find_row(df: pd.DataFrame | None, keys: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for key in keys:
        if key in df.index:
            return df.loc[key]
    return None


def _recent_years(df: pd.DataFrame, n: int = 4) -> pd.DataFrame:
    """최근 n개 연도(열)만 선택."""
    cols = sorted(df.columns, reverse=True)[:n]
    return df[cols].copy()


def extract_annual_series(
    financials: pd.DataFrame | None,
    balance_sheet: pd.DataFrame | None,
    cashflow: pd.DataFrame | None,
) -> dict[str, pd.Series]:
    """연도별 주요 계정 시계열 추출."""
    fin = _recent_years(financials) if financials is not None else None
    bal = _recent_years(balance_sheet) if balance_sheet is not None else None
    cf = _recent_years(cashflow) if cashflow is not None else None

    series: dict[str, pd.Series] = {}
    if fin is not None:
        for name, keys in [
            ("revenue", FINANCIAL_ROW_KEYS["revenue"]),
            ("operating_income", FINANCIAL_ROW_KEYS["operating_income"]),
            ("net_income", FINANCIAL_ROW_KEYS["net_income"]),
        ]:
            row = _find_row(fin, keys)
            if row is not None:
                series[name] = row

    if cf is not None:
        row = _find_row(cf, FINANCIAL_ROW_KEYS["operating_cashflow"])
        if row is not None:
            series["operating_cashflow"] = row

    if bal is not None:
        liab = _find_row(bal, FINANCIAL_ROW_KEYS["total_liabilities"])
        equity = _find_row(bal, FINANCIAL_ROW_KEYS["stockholders_equity"])
        if liab is not None and equity is not None:
            aligned = pd.concat([liab, equity], axis=1, keys=["liab", "equity"]).dropna()
            debt_ratio = aligned["liab"] / aligned["equity"].replace(0, pd.NA)
            series["debt_ratio"] = debt_ratio

        if "net_income" in series and equity is not None:
            ni = series["net_income"]
            common_idx = ni.index.intersection(equity.index)
            roe = (ni[common_idx] / equity[common_idx].replace(0, pd.NA)) * 100
            series["roe"] = roe

    return series


def build_metrics_table(series: dict[str, pd.Series]) -> pd.DataFrame:
    """주요 재무 지표 테이블 (행=지표, 열=연도)."""
    rows = []
    display_keys = [
        "revenue",
        "operating_income",
        "net_income",
        "operating_cashflow",
        "debt_ratio",
        "roe",
    ]

    for key in display_keys:
        if key not in series:
            continue
        s = series[key]
        label = METRIC_LABELS_KO[key]
        row = {col.strftime("%Y") if hasattr(col, "strftime") else str(col)[:4]: v for col, v in s.items()}
        row["지표"] = label
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("지표")
    year_cols = sorted([c for c in df.columns if c != "지표"], reverse=True)
    return df[year_cols]


def compute_annual_amounts_chart(series: dict[str, pd.Series]) -> pd.DataFrame:
    """매출·영업이익 바 차트용 long-format."""
    records = []
    for key, label in [("revenue", "매출액"), ("operating_income", "영업이익")]:
        if key not in series:
            continue
        for date_col, value in series[key].items():
            year = date_col.strftime("%Y") if hasattr(date_col, "strftime") else str(date_col)[:4]
            if pd.notna(value):
                records.append({"연도": year, "지표": label, "금액": float(value)})

    return pd.DataFrame(records)


def format_large_number(value: float) -> str:
    """큰 숫자를 읽기 쉬운 문자열로."""
    if pd.isna(value):
        return "-"
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"{value / 1e12:.2f}조"
    if abs_val >= 1e8:
        return f"{value / 1e8:.2f}억"
    if abs_val >= 1e4:
        return f"{value / 1e4:.2f}만"
    return f"{value:,.0f}"


def metrics_to_text(metrics_df: pd.DataFrame) -> str:
    """AI 컨텍스트용 재무 테이블 텍스트."""
    if metrics_df.empty:
        return "재무 데이터 없음"
    return metrics_df.to_string()
