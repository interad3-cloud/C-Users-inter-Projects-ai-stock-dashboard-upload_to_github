"""글로벌 매크로 대시보드 UI — 종목 검색과 무관하게 항상 표시."""

from __future__ import annotations

import streamlit as st

from charts import build_fear_greed_gauge, build_treasury_chart
from macro_data import MacroSnapshot, load_macro_snapshot
from ui_components import render_card_open, render_card_close, render_kpi_row, render_section_heading


def render_macro_dashboard() -> None:
    """매크로 지표 탭 — 독립 데이터 로드."""
    render_section_heading("글로벌 매크로 대시보드")
    st.markdown(
        '<p class="fin-caption">종목 분석과 별개로 최신 거시경제 지표를 제공합니다.</p>',
        unsafe_allow_html=True,
    )

    with st.spinner("매크로 데이터 불러오는 중..."):
        snapshot = load_macro_snapshot()

    if snapshot.errors:
        st.caption("일부 지표를 불러오지 못했습니다: " + ", ".join(snapshot.errors))

    st.caption(f"갱신: {snapshot.fetched_at}")

    # 공포/탐욕 + 10년물 금리
    col_fg, col_tnx = st.columns([1, 2], gap="medium")

    with col_fg:
        render_card_open("공포 · 탐욕 지수")
        if snapshot.fear_greed:
            fg = snapshot.fear_greed
            tone = _fear_greed_tone(fg.value)
            render_kpi_row([(fg.label, f"{fg.value}", tone)])
            fig_gauge = build_fear_greed_gauge(fg.value, fg.label)
            st.plotly_chart(fig_gauge, use_container_width=True, key="macro_fear_greed_gauge")
        else:
            st.warning("공포/탐욕 지수 데이터를 가져올 수 없습니다.")
        render_card_close()

    with col_tnx:
        render_card_open("미국 10년물 국채 금리 (^TNX)")
        if snapshot.treasury_rate is not None:
            tnx_tone = "up" if (snapshot.treasury_change_bps or 0) > 0 else "down"
            delta_txt = (
                f"{snapshot.treasury_change_bps:+.0f}bp"
                if snapshot.treasury_change_bps is not None
                else None
            )
            render_kpi_row(
                [
                    ("현재 금리", f"{snapshot.treasury_rate:.2f}%", None),
                    ("전일 대비", delta_txt or "N/A", tnx_tone if delta_txt else None),
                ]
            )
        if not snapshot.treasury_history.empty:
            fig_tnx = build_treasury_chart(snapshot.treasury_history)
            st.plotly_chart(fig_tnx, use_container_width=True, key="macro_treasury_chart")
        else:
            st.warning("국채 금리 차트 데이터를 가져올 수 없습니다.")
        render_card_close()

    # 핵심 경제 지표 카드
    render_section_heading("핵심 경제 지표", level=4)
    if snapshot.indicators:
        metric_items = []
        for ind in snapshot.indicators:
            display = ind.value
            if ind.delta:
                display = f"{ind.value} ({ind.delta})"
            metric_items.append((ind.name, display, ind.delta_tone))
        render_kpi_row(metric_items)

        cols = st.columns(len(snapshot.indicators), gap="small")
        for col, ind in zip(cols, snapshot.indicators):
            with col:
                render_card_open(ind.name, compact=True)
                st.markdown(f"**{ind.value}**")
                if ind.delta:
                    tone_cls = f"fin-badge fin-{ind.delta_tone}" if ind.delta_tone else "fin-caption"
                    st.markdown(f'<span class="{tone_cls}">{ind.delta}</span>', unsafe_allow_html=True)
                st.markdown(f'<p class="fin-caption">{ind.subtitle}</p>', unsafe_allow_html=True)
                render_card_close()
    else:
        st.info("경제 지표 데이터를 불러올 수 없습니다.")


def _fear_greed_tone(value: int) -> str | None:
    if value >= 55:
        return "up"
    if value <= 45:
        return "down"
    return None
