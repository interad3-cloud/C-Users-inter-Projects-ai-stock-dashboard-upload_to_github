"""Plotly 차트 생성."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from indicators import MaCrossover, compute_volume_profile

_CHART_COLORS = {
    "bg": "#FFFFFF",
    "grid": "#E8ECF0",
    "text": "#333333",
    "navy": "#003366",
    "ma20": "#FFB300",
    "ma60": "#1976D2",
    "rsi": "#F57C00",
    "macd": "#1976D2",
    "signal": "#E64A19",
    "up": "#2E7D32",
    "down": "#C62828",
}


def build_price_chart(
    price_df: pd.DataFrame,
    ma_df: pd.DataFrame,
    rsi: pd.Series,
    macd_df: pd.DataFrame,
    bb_df: pd.DataFrame,
    crossovers: list[MaCrossover] | None = None,
) -> go.Figure:
    """캔들스틱 + BB + MA20/60 + 매물대 + RSI + MACD (간결 레이아웃)."""
    crossovers = crossovers or []
    vp_centers, vp_volumes = compute_volume_profile(price_df, bins=30)

    fig = make_subplots(
        rows=3,
        cols=2,
        column_widths=[0.96, 0.04],
        shared_xaxes=False,
        shared_yaxes=False,
        vertical_spacing=0.09,
        row_heights=[0.62, 0.10, 0.10],
        specs=[
            [{}, {"rowspan": 1}],
            [{"colspan": 2}, None],
            [{"colspan": 2}, None],
        ],
        subplot_titles=("주가", None, "RSI (14)", "MACD"),
    )

    # 볼린저 밴드 — 배경만 (opacity 0.1)
    fig.add_trace(
        go.Scatter(
            x=bb_df.index,
            y=bb_df["Upper"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=bb_df.index,
            y=bb_df["Lower"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(0, 51, 102, 0.05)",
            name="볼린저 밴드",
            showlegend=False,
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Candlestick(
            x=price_df.index,
            open=price_df["Open"],
            high=price_df["High"],
            low=price_df["Low"],
            close=price_df["Close"],
            name="주가",
            increasing_line_color=_CHART_COLORS["up"],
            decreasing_line_color=_CHART_COLORS["down"],
            increasing_fillcolor=_CHART_COLORS["up"],
            decreasing_fillcolor=_CHART_COLORS["down"],
        ),
        row=1,
        col=1,
    )

    for col, color, label in [
        ("MA20", _CHART_COLORS["ma20"], "MA 20"),
        ("MA60", _CHART_COLORS["ma60"], "MA 60"),
    ]:
        if col in ma_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=ma_df.index,
                    y=ma_df[col],
                    mode="lines",
                    name=label,
                    line=dict(width=1.3, color=color),
                ),
                row=1,
                col=1,
            )

    for event in crossovers[-3:]:
        color = _CHART_COLORS["up"] if event.kind == "golden" else _CHART_COLORS["down"]
        arrow = "▲" if event.kind == "golden" else "▼"
        fig.add_trace(
            go.Scatter(
                x=[event.date],
                y=[event.price],
                mode="text",
                text=[arrow],
                textfont=dict(size=18, color=color),
                showlegend=False,
                hovertemplate=(
                    f"{event.date.strftime('%Y-%m-%d')}<br>"
                    f"{event.price:,.2f}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    if len(vp_centers) > 0 and vp_volumes.max() > 0:
        fig.add_trace(
            go.Bar(
                x=vp_volumes,
                y=vp_centers,
                orientation="h",
                name="매물대",
                marker_color="rgba(0, 51, 102, 0.18)",
                showlegend=False,
                hovertemplate="가격 %{y:,.2f}<br>거래량 %{x:,.0f}<extra></extra>",
            ),
            row=1,
            col=2,
        )

    fig.add_trace(
        go.Scatter(
            x=rsi.index,
            y=rsi,
            name="RSI",
            line=dict(color=_CHART_COLORS["rsi"], width=1.4),
        ),
        row=2,
        col=1,
    )
    for level in (70, 30):
        fig.add_hline(
            y=level,
            line_dash="dot",
            line_color="#B0BEC5",
            opacity=0.6,
            row=2,
            col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=macd_df.index,
            y=macd_df["MACD"],
            name="MACD",
            line=dict(color=_CHART_COLORS["macd"], width=1.2),
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=macd_df.index,
            y=macd_df["Signal"],
            name="Signal",
            line=dict(color=_CHART_COLORS["signal"], width=1.2),
        ),
        row=3,
        col=1,
    )
    hist_colors = [
        _CHART_COLORS["up"] if v >= 0 else _CHART_COLORS["down"]
        for v in macd_df["Histogram"].fillna(0)
    ]
    fig.add_trace(
        go.Bar(
            x=macd_df.index,
            y=macd_df["Histogram"],
            name="Histogram",
            marker_color=hist_colors,
            opacity=0.45,
            showlegend=False,
        ),
        row=3,
        col=1,
    )

    fig.update_layout(
        height=780,
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        paper_bgcolor=_CHART_COLORS["bg"],
        plot_bgcolor=_CHART_COLORS["bg"],
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=11, color=_CHART_COLORS["text"]),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="left",
            x=0,
            bgcolor="rgba(255,255,255,0.8)",
        ),
        margin=dict(l=48, r=12, t=48, b=32),
        barmode="overlay",
    )
    fig.update_xaxes(showticklabels=False, row=1, col=1, gridcolor=_CHART_COLORS["grid"])
    fig.update_xaxes(showticklabels=False, row=2, col=1, gridcolor=_CHART_COLORS["grid"])
    fig.update_yaxes(title_text="가격", row=1, col=1, gridcolor=_CHART_COLORS["grid"])
    fig.update_yaxes(showticklabels=False, row=1, col=2, matches="y")
    fig.update_xaxes(showticklabels=False, row=1, col=2)
    fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100], gridcolor=_CHART_COLORS["grid"])
    fig.update_yaxes(title_text="MACD", row=3, col=1, gridcolor=_CHART_COLORS["grid"])

    return fig


def build_forecast_bar_chart(
    historical_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> go.Figure | None:
    """과거 3개년 + 추정 3개년 매출·영업이익 6개년 바 차트."""
    if historical_df.empty and forecast_df.empty:
        return None

    combined = pd.concat([historical_df, forecast_df], ignore_index=True)
    fig = go.Figure()

    for metric, hist_color, fc_color in [
        ("매출액", "#42A5F5", "rgba(66, 165, 245, 0.45)"),
        ("영업이익", "#66BB6A", "rgba(102, 187, 106, 0.45)"),
    ]:
        for segment, color, label_suffix in [
            ("실적", hist_color, ""),
            ("추정", fc_color, " (추정)"),
        ]:
            sub = combined[(combined["구분"] == segment)]
            if sub.empty:
                continue
            fig.add_trace(
                go.Bar(
                    x=sub["연도"].astype(str),
                    y=sub[metric],
                    name=f"{metric}{label_suffix}",
                    marker_color=color,
                    legendgroup=metric,
                )
            )

    if not fig.data:
        return None

    fig.update_layout(
        title="매출·영업이익 6개년 추이 (실적 + 추정)",
        barmode="group",
        template="plotly_white",
        xaxis_title="연도",
        yaxis_title="금액",
        height=420,
        legend=dict(orientation="h", y=1.12),
    )
    return fig


def build_scenario_chart(scenarios: list, current_price: float) -> go.Figure:
    """Bull / Base / Bear 목표주가 비교 차트."""
    names = [s.label_ko for s in scenarios]
    prices = [s.y1_target_price for s in scenarios]
    colors = ["#66BB6A", "#42A5F5", "#EF5350"]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=names,
            y=prices,
            marker_color=colors,
            text=[f"{p:,.0f}" for p in prices],
            textposition="outside",
            name="Y+1 목표주가",
        )
    )
    fig.add_hline(
        y=current_price,
        line_dash="dash",
        line_color="#FFA726",
        annotation_text=f"현재가 {current_price:,.0f}",
    )
    fig.update_layout(
        title="시나리오별 Y+1 목표주가 (Bull / Base / Bear)",
        template="plotly_white",
        yaxis_title="주가",
        height=380,
        showlegend=False,
    )
    return fig


def build_target_price_chart(
    current_price: float,
    forecast_rows: list,
) -> go.Figure:
    """현재가 vs 향후 3개년 적정 예상 주가 라인 차트."""
    years = ["현재"] + [f"Y+{i}" for i in range(1, 4)]
    prices = [current_price] + [r.target_price for r in forecast_rows]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=years,
            y=prices,
            mode="lines+markers",
            name="적정 예상 주가",
            line=dict(color="#42A5F5", width=2.5),
            marker=dict(size=10),
        )
    )
    fig.add_hline(
        y=current_price,
        line_dash="dash",
        line_color="#FFA726",
        annotation_text=f"현재가 {current_price:,.2f}",
        annotation_position="right",
    )
    fig.update_layout(
        title="적정 예상 주가 추이 (Target PER 기반)",
        template="plotly_white",
        yaxis_title="주가",
        height=380,
        showlegend=True,
    )
    return fig


def build_revenue_profit_bar(chart_df: pd.DataFrame) -> go.Figure | None:
    """매출액·영업이익 연간 추이 바 차트."""
    if chart_df is None or chart_df.empty:
        return None

    fig = go.Figure()
    for metric, color in [("매출액", "#42A5F5"), ("영업이익", "#66BB6A")]:
        subset = chart_df[chart_df["지표"] == metric]
        if subset.empty:
            continue
        fig.add_trace(
            go.Bar(
                x=subset["연도"].astype(str),
                y=subset["금액"],
                name=metric,
                marker_color=color,
            )
        )

    if not fig.data:
        return None

    fig.update_layout(
        title="매출액 및 영업이익 추이",
        barmode="group",
        template="plotly_white",
        xaxis_title="연도",
        yaxis_title="금액",
        height=400,
        legend=dict(orientation="h", y=1.1),
    )
    return fig
