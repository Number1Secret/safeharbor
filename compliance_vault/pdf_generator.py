"""
PDF Audit Pack Generator

Generates professional PDF reports for IRS audit defense.
Uses ReportLab for PDF generation with cover page, TOC, and data sections.
"""

import io
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# Custom styles
BRAND_BLUE = colors.HexColor("#1e40af")
BRAND_DARK = colors.HexColor("#1e293b")
LIGHT_GRAY = colors.HexColor("#f1f5f9")


def _get_styles():
    """Get PDF paragraph styles."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=28,
        spaceAfter=12,
        textColor=BRAND_DARK,
    ))
    styles.add(ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontSize=14,
        spaceAfter=6,
        textColor=colors.gray,
    ))
    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=BRAND_BLUE,
        spaceBefore=24,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        "SubSection",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=BRAND_DARK,
        spaceBefore=12,
        spaceAfter=6,
    ))
    return styles


def generate_audit_pack_pdf(
    org_name: str,
    ein: str,
    tax_year: int,
    calculations: list[dict],
    employees: list[dict],
    vault_entries: list[dict],
    classifications: list[dict],
    retro_audit: dict | None = None,
) -> bytes:
    """
    Generate a complete Audit Defense Pack as a PDF.

    Returns the PDF as bytes ready for streaming.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = _get_styles()
    story = []

    # ── 1. Cover Page ──────────────────────────────
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph("SafeHarbor AI", styles["CoverTitle"]))
    story.append(Paragraph("OBBB Tax Compliance — Audit Defense Pack", styles["CoverSubtitle"]))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph(f"Organization: {org_name}", styles["Normal"]))
    story.append(Paragraph(f"EIN: {ein}", styles["Normal"]))
    story.append(Paragraph(f"Tax Year: {tax_year}", styles["Normal"]))
    story.append(Paragraph(
        f"Generated: {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}",
        styles["Normal"],
    ))
    story.append(Spacer(1, inch))
    story.append(Paragraph(
        "This document contains confidential tax compliance data prepared for "
        "IRS audit defense purposes under the One Big Beautiful Bill Act (OBBB).",
        styles["Normal"],
    ))
    story.append(PageBreak())

    # ── 2. Table of Contents ───────────────────────
    story.append(Paragraph("Table of Contents", styles["SectionHeader"]))
    toc_items = [
        "1. Executive Summary",
        "2. Calculation Run Summary",
        "3. Employee Roster & Classifications",
        "4. TTOC Classification Details",
        "5. Compliance Vault Chain",
        "6. Retro-Audit Report",
        "7. Methodology & Engine Versions",
    ]
    for item in toc_items:
        story.append(Paragraph(item, styles["Normal"]))
        story.append(Spacer(1, 4))
    story.append(PageBreak())

    # ── 3. Executive Summary ───────────────────────
    story.append(Paragraph("1. Executive Summary", styles["SectionHeader"]))
    total_ot = sum(Decimal(str(c.get("total_qualified_ot", 0))) for c in calculations)
    total_tips = sum(Decimal(str(c.get("total_qualified_tips", 0))) for c in calculations)
    total_credit = sum(Decimal(str(c.get("total_combined_credit", 0))) for c in calculations)

    summary_data = [
        ["Metric", "Value"],
        ["Total Calculation Runs", str(len(calculations))],
        ["Total Employees", str(len(employees))],
        ["Total Qualified Overtime", f"${total_ot:,.2f}"],
        ["Total Qualified Tips", f"${total_tips:,.2f}"],
        ["Total Combined Credit", f"${total_credit:,.2f}"],
        ["TTOC Classifications", str(len(classifications))],
        ["Vault Entries", str(len(vault_entries))],
    ]
    t = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ── 4. Calculation Run Summary ─────────────────
    story.append(Paragraph("2. Calculation Run Summary", styles["SectionHeader"]))
    if calculations:
        calc_data = [["Run ID", "Period", "Status", "Employees", "Credit"]]
        for c in calculations:
            calc_data.append([
                str(c.get("id", ""))[:8] + "...",
                f"{c.get('period_start', '')} - {c.get('period_end', '')}",
                c.get("status", ""),
                str(c.get("total_employees", 0)),
                f"${Decimal(str(c.get('total_combined_credit', 0))):,.2f}",
            ])
        t = Table(calc_data, colWidths=[1.2 * inch, 2 * inch, 1 * inch, 1 * inch, 1.3 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No calculation runs found for this tax year.", styles["Normal"]))
    story.append(PageBreak())

    # ── 5. Employee Roster ─────────────────────────
    story.append(Paragraph("3. Employee Roster & Classifications", styles["SectionHeader"]))
    if employees:
        emp_data = [["Name", "Job Title", "TTOC", "Filing Status", "Hourly Rate"]]
        for e in employees:
            emp_data.append([
                f"{e.get('first_name', '')} {e.get('last_name', '')}",
                e.get("job_title", ""),
                e.get("ttoc_code", "N/A"),
                e.get("filing_status", ""),
                f"${Decimal(str(e.get('hourly_rate', 0))):,.2f}",
            ])
        t = Table(emp_data, colWidths=[1.5 * inch, 1.5 * inch, 0.8 * inch, 1.2 * inch, 1 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    story.append(PageBreak())

    # ── 6. TTOC Classifications ────────────────────
    story.append(Paragraph("4. TTOC Classification Details", styles["SectionHeader"]))
    if classifications:
        cls_data = [["Employee", "TTOC Code", "Description", "Confidence", "Method"]]
        for c in classifications:
            cls_data.append([
                c.get("employee_name", ""),
                c.get("ttoc_code", ""),
                c.get("ttoc_description", "")[:30],
                f"{c.get('confidence', 0):.0%}",
                c.get("method", ""),
            ])
        t = Table(cls_data, colWidths=[1.3 * inch, 0.9 * inch, 2 * inch, 0.9 * inch, 0.9 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No TTOC classifications available.", styles["Normal"]))
    story.append(PageBreak())

    # ── 7. Vault Chain ─────────────────────────────
    story.append(Paragraph("5. Compliance Vault Chain", styles["SectionHeader"]))
    story.append(Paragraph(
        "The compliance vault maintains an immutable hash chain of all calculation events. "
        "Each entry's hash is computed from its content plus the previous entry's hash, "
        "ensuring tamper-evidence.",
        styles["Normal"],
    ))
    story.append(Spacer(1, 12))

    if vault_entries:
        vault_data = [["Seq", "Type", "Hash (first 16)", "Created"]]
        for v in vault_entries[:50]:  # Limit to 50 entries
            vault_data.append([
                str(v.get("sequence_number", "")),
                v.get("entry_type", ""),
                v.get("entry_hash", "")[:16] + "...",
                v.get("created_at", "")[:19],
            ])
        t = Table(vault_data, colWidths=[0.6 * inch, 1.5 * inch, 2 * inch, 1.8 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Courier"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
    story.append(PageBreak())

    # ── 8. Retro-Audit ─────────────────────────────
    story.append(Paragraph("6. Retro-Audit Report", styles["SectionHeader"]))
    if retro_audit:
        story.append(Paragraph(
            f"Risk Level: {retro_audit.get('overall_risk', 'N/A')}",
            styles["SubSection"],
        ))
        story.append(Paragraph(
            f"Total Discrepancy: ${Decimal(str(retro_audit.get('total_discrepancy', 0))):,.2f}",
            styles["Normal"],
        ))
        findings = retro_audit.get("findings", [])
        if findings:
            story.append(Spacer(1, 8))
            for f in findings:
                story.append(Paragraph(
                    f"- [{f.get('severity', '')}] {f.get('description', '')}",
                    styles["Normal"],
                ))
    else:
        story.append(Paragraph("No retro-audit data available.", styles["Normal"]))
    story.append(PageBreak())

    # ── 9. Methodology ─────────────────────────────
    story.append(Paragraph("7. Methodology & Engine Versions", styles["SectionHeader"]))
    story.append(Paragraph(
        "SafeHarbor AI calculates qualified amounts for OBBB tax exemptions using "
        "the following methodology:",
        styles["Normal"],
    ))
    story.append(Spacer(1, 8))
    methods = [
        "Regular Rate Engine: FLSA Section 7 weighted average calculation including "
        "all non-excludable compensation components.",
        "Tip Credit Engine: Qualified tip identification per OBBB guidelines with "
        "dual-job apportionment for mixed-role employees.",
        "Phase-Out Filter: MAGI-based phase-out calculation per filing status "
        "with linear reduction between threshold boundaries.",
        "Occupation AI: Claude-powered TTOC classification with O*NET crosswalk "
        "validation and human-in-the-loop review.",
    ]
    for m in methods:
        story.append(Paragraph(f"  {m}", styles["Normal"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 24))
    story.append(Paragraph(
        "--- End of Audit Defense Pack ---",
        styles["Normal"],
    ))

    # Build PDF
    doc.build(story)
    return buffer.getvalue()
