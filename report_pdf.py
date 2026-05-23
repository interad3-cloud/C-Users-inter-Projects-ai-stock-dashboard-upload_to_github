"""증권사 리포트 PDF 생성 (reportlab)."""

from __future__ import annotations

import io
import os
import platform
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from paths import asset_path
from research_report import ResearchReport, _fmt_price


def _korean_font_candidates() -> list[Path]:
    """프로젝트 assets → Linux(Cloud) → OS 기본 폰트 순으로 탐색."""
    candidates: list[Path] = []

    fonts_dir = asset_path("fonts")
    if fonts_dir.is_dir():
        candidates.extend(sorted(fonts_dir.glob("*.ttf")))
        candidates.extend(sorted(fonts_dir.glob("*.otf")))

    candidates.extend(
        [
            Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
            Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        ]
    )

    if platform.system() == "Windows":
        win_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        candidates.extend([win_fonts / "malgun.ttf", win_fonts / "malgunbd.ttf"])

    if platform.system() == "Darwin":
        candidates.append(Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"))

    return candidates


def _register_korean_font() -> str:
    """한글 TTF 폰트 등록 (프로젝트 assets/fonts 우선)."""
    for path in _korean_font_candidates():
        if not path.exists():
            continue
        name = "KoreanFont"
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
            return name
        except Exception:
            continue
    return "Helvetica"


def generate_report_pdf(report: ResearchReport) -> bytes:
    """리서치 리포트 PDF 바이트 생성."""
    buffer = io.BytesIO()
    font_name = _register_korean_font()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleKR",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=14,
        textColor=colors.HexColor("#003366"),
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyKR",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=14,
        spaceAfter=8,
    )
    head_style = ParagraphStyle(
        "HeadKR",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=10,
        textColor=colors.HexColor("#003366"),
        spaceBefore=12,
        spaceAfter=6,
    )

    story = []

    story.append(
        Paragraph(
            f"{report.company_name} ({report.ticker})",
            title_style,
        )
    )
    story.append(
        Paragraph(
            f"{report.report_type} | {report.sector} | {report.report_date}",
            body_style,
        )
    )
    story.append(
        Paragraph(
            f"<b>{report.rating_en}</b> · "
            f"목표주가 {_fmt_price(report.target_price, report.currency)} · "
            f"현재주가 {_fmt_price(report.current_price, report.currency)} · "
            f"상승여력 {report.upside_pct:+.1f}%",
            body_style,
        )
    )
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(f"Investment Points — {report.recent_review_title}", head_style))
    story.append(Paragraph(report.recent_review_body, body_style))

    if report.forecast.analysis and report.forecast.analysis.consensus.available:
        c = report.forecast.analysis.consensus
        story.append(
            Paragraph(
                f"<b>{c.surprise_label}</b> — EPS 서프라이즈 {c.eps_surprise_pct:+.1f}%",
                body_style,
            )
        )

    for i, pt in enumerate(report.investment_points, 1):
        story.append(Paragraph(f"{i}. {pt}", body_style))

    for sec_title, sec_body in report.sections.items():
        story.append(Paragraph(sec_title, head_style))
        story.append(Paragraph(sec_body.replace("\n", "<br/>"), body_style))

    if not report.forecast.scenario_table.empty:
        story.append(Paragraph("Scenario Analysis — Bull / Base / Bear", head_style))
        sc_data = [[""] + list(report.forecast.scenario_table.columns)]
        for _, row in report.forecast.scenario_table.iterrows():
            cells = [str(row["시나리오"]) if "시나리오" in row.index else ""]
            for c in report.forecast.scenario_table.columns:
                if c == "시나리오":
                    continue
                v = row[c]
                cells.append(f"{v:,.2f}" if isinstance(v, (int, float)) else str(v))
            sc_data.append(cells)
        t2 = Table(sc_data, repeatRows=1)
        t2.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ]))
        story.append(t2)
        story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(f"Financial Data ({report.unit_label})", head_style))
    fin_df = report.financial_table.round(2)
    table_data = [[""] + list(fin_df.columns)]
    for idx, row in fin_df.iterrows():
        cells = [str(idx)]
        for col in fin_df.columns:
            v = row[col]
            cells.append("-" if v != v else f"{v:,.2f}")
        table_data.append(cells)

    t = Table(table_data, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Valuation — 목표주가 산출", head_style))
    story.append(Paragraph(report.valuation_text, body_style))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(report.compliance, body_style))

    doc.build(story)
    return buffer.getvalue()
