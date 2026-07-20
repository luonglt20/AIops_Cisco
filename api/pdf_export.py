"""
MerakiMind — PDF Report Exporter
Xuất báo cáo nhân sự và prompt kỹ thuật ra file PDF.
Dùng reportlab (pure Python, không cần browser/wkhtmltopdf).
"""
import io
import os
from datetime import datetime, timezone

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table,
        TableStyle, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False


# ── Font Configurations (Unicode support) ──────────────────────────────────────
FONT_NAME = "Helvetica"
FONT_BOLD_NAME = "Helvetica-Bold"
FONT_CODE_NAME = "Courier"

if _PDF_AVAILABLE:
    # Use Arial for Vietnamese Unicode support on macOS
    arial_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    arial_bold_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    courier_path = "/System/Library/Fonts/Supplemental/Courier New.ttf"
    
    if os.path.exists(arial_path) and os.path.exists(arial_bold_path):
        try:
            pdfmetrics.registerFont(TTFont("Arial", arial_path))
            pdfmetrics.registerFont(TTFont("Arial-Bold", arial_bold_path))
            FONT_NAME = "Arial"
            FONT_BOLD_NAME = "Arial-Bold"
            print("[PDF] Registered Arial & Arial-Bold fonts for Vietnamese Unicode support.")
        except Exception as e:
            print(f"[PDF] Failed to register Arial font: {e}")
            
    if os.path.exists(courier_path):
        try:
            pdfmetrics.registerFont(TTFont("CourierNew", courier_path))
            FONT_CODE_NAME = "CourierNew"
            print("[PDF] Registered CourierNew font for Vietnamese Monospace Unicode support.")
        except Exception as e:
            print(f"[PDF] Failed to register CourierNew font: {e}")
            FONT_CODE_NAME = FONT_NAME
    else:
        FONT_CODE_NAME = FONT_NAME


# ── Color Palette ──────────────────────────────────────────────────────────────
NAVY    = colors.HexColor("#0c2340")
TEAL    = colors.HexColor("#00a0e4")
LIGHT   = colors.HexColor("#f4f7fb")
ACCENT  = colors.HexColor("#16a34a")
RED     = colors.HexColor("#dc2626")
GRAY    = colors.HexColor("#6b7280")


def generate_pdf(pipeline_result: dict) -> bytes | None:
    """
    Generate a PDF report from the pipeline result dict.
    Returns PDF bytes or None if reportlab is unavailable.
    """
    if not _PDF_AVAILABLE:
        print("[PDF] reportlab not installed. Cannot generate PDF.")
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="MerakiMind — Incident Report",
    )

    styles  = getSampleStyleSheet()
    story   = []

    # ── Styles ─────────────────────────────────────────────────────────────────
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18, fontName=FONT_BOLD_NAME,
                         textColor=NAVY, spaceAfter=4, spaceBefore=0, leading=22)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, fontName=FONT_BOLD_NAME,
                         textColor=TEAL, spaceAfter=4, spaceBefore=12, leading=16)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, fontName=FONT_NAME,
                           textColor=colors.black, leading=14, spaceAfter=4)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=7, fontName=FONT_NAME,
                            textColor=GRAY, leading=11)
    code_style = ParagraphStyle("Code", parent=styles["Normal"], fontSize=7.5,
                                 fontName=FONT_CODE_NAME, textColor=colors.HexColor("#1e293b"),
                                 backColor=LIGHT, leading=12, leftIndent=8)

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    alert   = pipeline_result.get("alert", {})
    report  = pipeline_result.get("report", "")
    prompt  = pipeline_result.get("prompt", pipeline_result.get("prompt_groq", ""))

    # ── Header ─────────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph("<b>MERAKIMIND</b>", ParagraphStyle(
            "BrandH", fontName=FONT_BOLD_NAME, fontSize=22,
            textColor=NAVY)),
        Paragraph(f"<font color='#6b7280' size='8'>AI Network Intelligence<br/>"
                  f"Cisco Meraki Diagnostic Platform</font>",
                  ParagraphStyle("BrandSub", fontName=FONT_NAME, fontSize=8, textColor=GRAY, leading=12)),
        Paragraph(f"<font size='8' color='#6b7280'>Xuất lúc<br/><b>{now_str}</b></font>",
                  ParagraphStyle("Date", fontName=FONT_NAME, fontSize=8, textColor=GRAY, alignment=TA_RIGHT, leading=12)),
    ]]
    header_tbl = Table(header_data, colWidths=["35%", "40%", "25%"])
    header_tbl.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",   (0, 0), (-1, 0),  0.5, NAVY),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── Severity Badge Row ─────────────────────────────────────────────────────
    sev    = pipeline_result.get("severity", alert.get("severity", "HIGH"))
    sev_color = RED if sev == "HIGH" else colors.HexColor("#f59e0b")
    sev_data = [[
        Paragraph(f"<b>📋 BÁO CÁO SỰ CỐ MẠNG</b>", h1),
        Paragraph(f"<b>{sev}</b>",
                  ParagraphStyle("Badge", fontName=FONT_BOLD_NAME, fontSize=10,
                                 textColor=colors.white, backColor=sev_color,
                                 alignment=TA_CENTER, borderPadding=4)),
    ]]
    sev_tbl = Table(sev_data, colWidths=["80%", "20%"])
    sev_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(sev_tbl)
    story.append(Spacer(1, 0.2*cm))

    # ── Device Info Table ──────────────────────────────────────────────────────
    story.append(Paragraph("📡 Thông tin thiết bị", h2))
    dev_name  = alert.get("device", pipeline_result.get("device_name", "N/A"))
    model     = alert.get("model", "N/A")
    serial    = alert.get("serial", "N/A")
    issue     = alert.get("issue", "N/A")
    last_seen = alert.get("lastSeen", pipeline_result.get("generated_at", "N/A"))[:19]
    org_name  = pipeline_result.get("org_name", "N/A")

    info_rows = [
        ["Tên thiết bị", dev_name, "Model",   model],
        ["Serial",       serial,   "Tổ chức", org_name],
        ["Loại sự cố",   issue,    "Thời điểm", last_seen],
    ]
    info_tbl = Table(info_rows, colWidths=["22%", "28%", "22%", "28%"])
    info_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1), LIGHT),
        ("BACKGROUND",   (2, 0), (2, -1), LIGHT),
        ("FONTNAME",     (0, 0), (-1, -1), FONT_NAME),
        ("FONTNAME",     (0, 0), (0, -1), FONT_BOLD_NAME),
        ("FONTNAME",     (2, 0), (2, -1), FONT_BOLD_NAME),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("GRID",         (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.3*cm))

    # ── HR Report Section ──────────────────────────────────────────────────────
    if report:
        story.append(HRFlowable(width="100%", thickness=1, color=TEAL))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("📄 Báo cáo Nhân sự (Dành cho Quản lý)", h2))
        for line in report.strip().split("\n"):
            stripped = line.strip()
            if not stripped:
                story.append(Spacer(1, 0.1*cm))
                continue
            # Bold section headers
            if stripped.startswith(("1.", "2.", "3.", "4.")) and len(stripped) < 80:
                story.append(Paragraph(f"<b>{stripped}</b>", body))
            else:
                story.append(Paragraph(stripped, body))
        story.append(Spacer(1, 0.3*cm))

    # ── Agent Notes ────────────────────────────────────────────────────────────
    agent_notes = pipeline_result.get("agent_notes", [])
    if agent_notes:
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("🤖 Tóm tắt từ AI Agents", h2))
        for note in agent_notes:
            story.append(Paragraph(f"• {note}", small))
        story.append(Spacer(1, 0.3*cm))

    # ── Technical Prompt Section ───────────────────────────────────────────────
    if prompt:
        story.append(HRFlowable(width="100%", thickness=1, color=NAVY))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("🛠️ Prompt Kỹ thuật (Dành cho Meraki AI Assistant)", h2))
        # Split into lines, truncate at 1000 chars for PDF readability
        for line in prompt[:2000].split("\n"):
            story.append(Paragraph(line or " ", code_style))
        if len(prompt) > 2000:
            story.append(Paragraph("... [Prompt đầy đủ trên Dashboard]", small))

    # ── Footer ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    story.append(Spacer(1, 0.2*cm))
    footer_text = (
        f"<font size='7' color='#6b7280'>Được tạo tự động bởi <b>MerakiMind AI Platform</b> · "
        f"Cisco Meraki Network Intelligence · {now_str} · "
        f"Tài liệu nội bộ — không phổ biến bên ngoài tổ chức</font>"
    )
    story.append(Paragraph(footer_text, ParagraphStyle("Footer", fontName=FONT_NAME, alignment=TA_CENTER, fontSize=7, textColor=GRAY)))

    doc.build(story)
    return buf.getvalue()


def save_pdf(pipeline_result: dict, output_dir: str = None) -> str | None:
    """
    Generate and save PDF to disk. Returns file path or None.
    """
    pdf_bytes = generate_pdf(pipeline_result)
    if not pdf_bytes:
        return None

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "reports")
    os.makedirs(output_dir, exist_ok=True)

    ts    = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dev   = pipeline_result.get("alert", {}).get("device", "device").replace(" ", "_")[:20]
    fname = f"MerakiMind_Report_{dev}_{ts}.pdf"
    fpath = os.path.join(output_dir, fname)

    with open(fpath, "wb") as f:
        f.write(pdf_bytes)
    print(f"[PDF] Saved to {fpath}")
    return fpath
