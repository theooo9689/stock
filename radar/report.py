from __future__ import annotations

import json
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
    assets = report["assets"]
    buys = sorted([a for a in assets if a["ranking"]["decision"] == "COMPRAR PARCIALMENTE"], key=lambda a: -a["ranking"]["score"])
    wait = sorted([a for a in assets if a["ranking"]["decision"] == "AGUARDAR"], key=lambda a: -a["ranking"]["score"])
    news = report["research"]["news"]
    lines = [f"RADAR DE INVESTIMENTOS — {report['day']}", f"Status: {report['status'].upper()}", "", "O QUE ACONTECEU HOJE"]
    lines += [f"• {n['title']} — {n['interpretation']}\n{n['evidence']['source_url']}" for n in news[:5]] or ["Sem notícia relevante confirmada pela pesquisa disponível."]
    lines += ["", "OPORTUNIDADES"]
    lines += [f"• {a['symbol']}: compra parcial; {a.get('thesis', {}).get('valuation_context', 'ver cenário e riscos no PDF')}" for a in buys[:3]] or ["Nenhuma compra atingiu os critérios com dados suficientes."]
    if not buys:
        lines += [f"• Investigar {a['symbol']}: {a.get('thesis', {}).get('wait_condition', 'aguardar dados e confirmação')}" for a in wait[:3]]
    lines += ["", "MELHOR ESPERAR"]
    lines += [f"• {a['symbol']}: " + ("; ".join(a["ranking"]["blockers"]) or a.get("thesis", {}).get("wait_condition", "Preço/risco não atingiu os critérios")) for a in wait[:3]]
    lines += ["", "RISCOS DO MOMENTO"] + ["• " + x for x in report["research"]["risks"][:3]]
    lines += ["", "O QUE MUDOU DESDE O RELATÓRIO ANTERIOR"] + ([f"• {d['symbol']}: {d['before']} → {d['after']}" for d in report["changes"][:8]] or [report["comparison_note"]])
    lines += ["", "PRÓXIMOS EVENTOS"] + ([f"• {e['published_at']}: {e['fact']}\n{e['source_url']}" for e in report["research"]["events"][:5]] or ["Agenda não confirmada nas fontes disponíveis; consultar PDF."])
    lines += ["", "Bolsas: conferir horário do último pregão no PDF. Cripto: negociação 24/7. Análise informativa, sem garantia de retorno."]
    ranking = [f"RANKING — {report['day']}", "Pontuação: soma ponderada; lacunas reduzem cobertura e podem impedir compra."]
    for name, categories in [("AÇÕES AMERICANAS", ("stocks",)), ("ETFs", ("us_etfs", "br_etfs")), ("CRIPTOMOEDAS", ("crypto",))]:
        ranking.append("\n" + name)
        for a in sorted([a for a in assets if a["category"] in categories], key=lambda a: -a["ranking"]["score"]):
            r = a["ranking"]
            reason = "; ".join(r["blockers"]) or a.get("thesis", {}).get("wait_condition", "Ver premissas e riscos no PDF")
            ranking.append(f"{a['symbol']} — {r['decision']} ({r['score']:.1f}/100; cobertura {r['coverage']:.0%})\n{reason}")
    return "\n".join(lines), "\n".join(ranking)


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
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    prefix = "demonstracao-" if report.get("demo") else "radar-"
    stem = prefix + report["day"]
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), undefined=StrictUndefined,
                      autoescape=False, trim_blocks=True, lstrip_blocks=True)
    env.filters["fmt"] = fmt
    env.filters["metric_table"] = metric_table
    text = env.get_template("report.md.j2").render(r=report)
    md, pdf, data = [directory / (stem + ext) for ext in (".md", ".pdf", ".json")]
    md.write_text(text)
    data.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    render_pdf(text, pdf)
    return {"markdown": md, "pdf": pdf, "json": data}
