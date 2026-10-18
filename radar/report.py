from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether


def fmt(value):
    if value is None:
        return "não disponível"
    if isinstance(value, float):
        return f"{value:,.5g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def metric_table(mapping):
    if not mapping:
        return "Métricas indisponíveis."
    rows = ["| Métrica | Valor |", "| --- | --- |"]
    for key, value in mapping.items():
        rows.append("| " + str(key).replace("|", "/") + " | " + fmt(value).replace("|", "/").replace("\n", " ") + " |")
    return "\n".join(rows)


def summaries(report):
    from .premium import upgrade_report
    from .presentation import messages
    if report.get('methodology_version') != 'premium-2.0':
        report = upgrade_report(report)
    return messages(report)


def render_pdf(markdown, path):
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold_path = font_path.with_name("DejaVuSans-Bold.ttf")
    font = "Helvetica"
    if font_path.exists():
        if "RadarSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("RadarSans", str(font_path)))
            pdfmetrics.registerFont(TTFont("RadarSansBold", str(bold_path)))
        font = "RadarSans"
    styles = getSampleStyleSheet()
    body = ParagraphStyle("RadarBody", fontName=font, fontSize=9, leading=13, spaceAfter=6,
                          wordWrap="LTR", splitLongWords=True, allowWidows=0, allowOrphans=0)
    h1 = ParagraphStyle("RadarH1", parent=body, fontName="RadarSansBold" if font == "RadarSans" else "Helvetica-Bold",
                        fontSize=15, leading=19, spaceBefore=14, spaceAfter=10)
    h2 = ParagraphStyle("RadarH2", parent=h1, fontSize=11, leading=15)
    cell = ParagraphStyle("RadarCell", parent=body, fontSize=7.5, leading=10, spaceAfter=0)
    story = []
    for block in markdown.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("| "):
            rows = []
            for line in block.splitlines():
                if not line.startswith("|") or re.fullmatch(r"[|\- :]+", line):
                    continue
                values = [v.strip() for v in line.strip("|").split("|")]
                rows.append([Paragraph(escape(v), cell) for v in values])
            if rows:
                table = Table(rows, colWidths=[48*mm, 76*mm], repeatRows=1, hAlign="LEFT", splitInRow=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0,0),(-1,0), colors.HexColor("#e2e8f0")),
                    ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("VALIGN", (0,0),(-1,-1), "TOP"),
                    ("LINEBELOW", (0,0),(-1,0), .5, colors.HexColor("#64748b")),
                    ("LEFTPADDING", (0,0),(-1,-1), 4), ("RIGHTPADDING", (0,0),(-1,-1), 4),
                ]))
                story.extend([table, Spacer(1, 6)])
            continue
        if block.startswith("# "):
            style, text = h1, block[2:]
        elif block.startswith("## "):
            style, text = h2, block[3:]
        else:
            style, text = body, block
        text = escape(text).replace("\n", "<br/>")
        # Paragraph handles long links and flowing text across pages, without fixed-height clipping.
        story.append(Paragraph(text, style))

    def page(canvas, doc):
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(12*mm, 8*mm, "Radar de investimentos | Fontes e horários no relatório")
        canvas.drawRightString(A5[0]-12*mm, 8*mm, str(doc.page))

    doc = SimpleDocTemplate(str(path), pagesize=A5, rightMargin=12*mm, leftMargin=12*mm,
                           topMargin=12*mm, bottomMargin=16*mm, title="Radar de Investimentos", author="Radar de Investimentos")
    doc.build(story, onFirstPage=page, onLaterPages=page)


def generate(report, directory):
    from .premium import upgrade_report
    from .premium_pdf import render
    from .presentation import preview
    if report.get('methodology_version') != 'premium-2.0':
        report = upgrade_report(report)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    prefix = 'demonstracao-premium-' if report.get('demo') else 'radar-premium-'
    output_hash=hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()[:8]
    stem = prefix + report['day'] + '-' + report['snapshot_id'][:8]+'-'+output_hash
    paths = {k:directory/(stem+ext) for k,ext in [('markdown','.md'),('pdf','.pdf'),('json','.json'),('telegram_preview','.html')]}
    env = Environment(loader=FileSystemLoader(Path(__file__).parent/'templates'), undefined=StrictUndefined, autoescape=False)
    env.filters['fmt'] = fmt
    paths['markdown'].write_text(env.get_template('premium.md.j2').render(r=report), encoding='utf-8')
    paths['json'].write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False), encoding='utf-8')
    render(report, paths['pdf'])
    preview(report, paths['telegram_preview'])
    return paths
