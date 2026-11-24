"""PDF Report Generator for Originality & Integrity Platform.

Produces a publication-quality multi-page PDF summary including:
1. Executive Header & Metadata.
2. Prominent Ethical Disclaimer ("Estimate only, not proof").
3. Scorecard (AI Probability, Similarity Index, Tamper Red Flags).
4. Integrity Flags & Anti-Tamper Evasion details.
5. AI Writing Analysis & GLTR token distribution summary.
6. Similarity & Plagiarism matched sources breakdown.
"""

import io
from typing import Any, Dict
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable


def generate_pdf_report(report_data: Dict[str, Any], output_stream: io.BytesIO = None) -> io.BytesIO:
    """Generate a PDF report stream from a unified report JSON dict."""
    if output_stream is None:
        output_stream = io.BytesIO()

    doc = SimpleDocTemplate(
        output_stream,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=6,
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#92400e"),
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )
    table_header = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#ffffff"),
    )

    story = []

    meta = report_data.get("metadata", {})
    integrity = report_data.get("integrity", {})
    ai = report_data.get("ai_detection", {})
    similarity = report_data.get("similarity", {})
    summary = report_data.get("summary", {})

    filename = meta.get("filename", "document.pdf")
    student = meta.get("student_name", "Student")
    words = meta.get("clean_word_count", 0)
    ai_pct = summary.get("ai_probability_pct", int((ai.get("document_ai_probability") or 0.0) * 100))
    sim_pct = summary.get("similarity_pct", int((similarity.get("overall_similarity") or 0.0) * 100))
    flag_count = summary.get("flag_count", integrity.get("flag_count", len(integrity.get("flags", []))))

    # 1. Title Banner
    story.append(Paragraph("Originality & Academic Integrity Analysis", title_style))
    story.append(
        Paragraph(
            f"File: <b>{filename}</b> &bull; Student: <b>{student}</b> &bull; Clean Words: <b>{words}</b>",
            subtitle_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=10))

    # 2. Ethical Disclaimer Box
    disclaimer_html = (
        "<b>Important Notice: Statistical Estimate Only &bull; Not Proof of Misconduct</b><br/>"
        "AI writing scores and similarity metrics are statistical indicators calibrated for low false-positive rates "
        "(&le; 1–2%), but must never be used as the sole basis for disciplinary action. Faculty should review "
        "highlighted passages and interview the student before drawing any academic conclusions."
    )
    disclaimer_table = Table([[Paragraph(disclaimer_html, disclaimer_style)]], colWidths=[540])
    disclaimer_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7")),
            ("BORDER", (0, 0), (-1, -1), 1, colors.HexColor("#f59e0b")),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(disclaimer_table)
    story.append(Spacer(1, 12))

    # 3. Top Metrics Summary Scorecard
    ai_status = "LIKELY HUMAN" if ai_pct <= 30 else ("SUSPECTED AI" if ai_pct >= 70 else "UNCLEAR")
    if ai.get("status") == "TOO_SHORT":
        ai_status = "TOO SHORT"

    scorecard_data = [
        [
            Paragraph("<b>AI Writing Probability</b>", table_header),
            Paragraph("<b>Plagiarism Similarity</b>", table_header),
            Paragraph("<b>Integrity & Evasion Flags</b>", table_header),
        ],
        [
            Paragraph(f"<font size=18><b>{ai_pct}%</b></font><br/>{ai_status}", table_cell),
            Paragraph(f"<font size=18><b>{sim_pct}%</b></font><br/>Total Archive Overlap", table_cell),
            Paragraph(f"<font size=18><b>{flag_count}</b></font><br/>{'Tampering Incidents' if flag_count else 'Verified Clean'}", table_cell),
        ],
    ]
    score_table = Table(scorecard_data, colWidths=[180, 180, 180])
    score_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("PADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(score_table)
    story.append(Spacer(1, 14))

    # 4. Integrity & Anti-Tamper Evasion Section
    story.append(Paragraph("1. Document Integrity & Anti-Tampering Analysis", section_heading))
    flags = integrity.get("flags", [])
    if not flags:
        story.append(
            Paragraph(
                "&#10003; <b>Clean Document:</b> No hidden white text, microscopic fonts (&le; 1pt), zero-width characters, "
                "or Cyrillic/Greek homoglyph substitutions detected.",
                body_style,
            )
        )
    else:
        flags_data = [
            [
                Paragraph("<b>Flag Type</b>", table_header),
                Paragraph("<b>Severity</b>", table_header),
                Paragraph("<b>Offset</b>", table_header),
                Paragraph("<b>Details / Context Snippet</b>", table_header),
            ]
        ]
        for f in flags[:8]:
            snippet_str = f.get("snippet", "")
            if len(snippet_str) > 40:
                snippet_str = snippet_str[:40] + "..."
            flags_data.append([
                Paragraph(f.get("flag_type", "ANOMALY"), table_cell),
                Paragraph(f.get("severity", "HIGH"), table_cell),
                Paragraph(str(f.get("offset", f.get("start_char", 0))), table_cell),
                Paragraph(f"{f.get('details', '')} [<i>{snippet_str}</i>]", table_cell),
            ])
        flags_table = Table(flags_data, colWidths=[140, 70, 50, 280])
        flags_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dc2626")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        story.append(flags_table)
    story.append(Spacer(1, 12))

    # 5. Multi-Signal AI Writing Analysis & GLTR
    story.append(Paragraph("2. Multi-Signal AI Writing Detection", section_heading))
    gltr = ai.get("gltr_summary", {})
    t10 = round((gltr.get("top10_pct") or 0.0) * 100)
    t100 = round((gltr.get("top100_pct") or 0.0) * 100)
    t1000 = round((gltr.get("top1000_pct") or 0.0) * 100)
    trest = round((gltr.get("rest_pct") or 0.0) * 100)

    ai_desc = (
        f"<b>Curvature Ensemble:</b> Analyzed across {ai.get('chunks_analyzed', 1)} chunks. "
        f"Primary Signal: {round((ai.get('primary_score') or 0.0)*100, 1)}%.<br/>"
        f"<b>GLTR Forensic Rank Distribution:</b> Top-10: <b>{t10}%</b> | Top-100: <b>{t100}%</b> | "
        f"Top-1000: <b>{t1000}%</b> | Rest (Rare words): <b>{trest}%</b>.<br/>"
        "<i>(AI generated text exhibits high Top-10 concentration (&ge; 70%), whereas natural human text demonstrates diverse rare vocabulary.)</i>"
    )
    story.append(Paragraph(ai_desc, body_style))
    story.append(Spacer(1, 12))

    # 6. Similarity & Plagiarism Breakdown
    story.append(Paragraph("3. Institutional Similarity & Overlap Analysis", section_heading))
    matches = similarity.get("matches", similarity.get("matched_sources", []))
    exact_pct = round((similarity.get("exact_similarity") or 0.0) * 100, 1)
    sem_pct = round((similarity.get("semantic_similarity") or 0.0) * 100, 1)

    story.append(
        Paragraph(
            f"Overall Similarity: <b>{sim_pct}%</b> (Exact Copying: <b>{exact_pct}%</b>, Paraphrase Overlap: <b>{sem_pct}%</b>).",
            body_style,
        )
    )
    story.append(Spacer(1, 4))

    if not matches:
        story.append(
            Paragraph(
                "&#10003; <b>No Overlapping Sources Found:</b> The document exhibits original phrasing with no matches in the institutional repository.",
                body_style,
            )
        )
    else:
        match_rows = [
            [
                Paragraph("<b>Matched Source</b>", table_header),
                Paragraph("<b>Type</b>", table_header),
                Paragraph("<b>Overlap %</b>", table_header),
                Paragraph("<b>Matched Fragment Excerpt</b>", table_header),
            ]
        ]
        for m in matches[:6]:
            span = m.get("student_span", {})
            text_snip = span.get("text", m.get("snippet", ""))
            if len(text_snip) > 50:
                text_snip = text_snip[:50] + "..."
            match_rows.append([
                Paragraph(m.get("source_title", m.get("source_id", "Archive Document")), table_cell),
                Paragraph(m.get("match_type", "exact").upper(), table_cell),
                Paragraph(f"{round((m.get('similarity') or 0.8)*100)}%", table_cell),
                Paragraph(f'"{text_snip}"', table_cell),
            ])
        match_table = Table(match_rows, colWidths=[150, 70, 60, 260])
        match_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        story.append(match_table)

    doc.build(story)
    output_stream.seek(0)
    return output_stream
