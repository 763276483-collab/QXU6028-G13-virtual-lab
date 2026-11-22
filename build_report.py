from pathlib import Path
import json
from xml.sax.saxutils import escape

import numpy as np
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, KeepTogether, Image
from figures import make_figures

root=Path(__file__).resolve().parent
gen=root/"generated"
result=json.loads((gen/"results.json").read_text())
metrics=json.loads((gen/"analysis_metrics.json").read_text())
with np.load(gen/"plot_data.npz") as data:
    figures=make_figures(dict(data),result,metrics)
font_dir = Path("C:/Windows/Fonts")
font_pair = [(font_dir/"arial.ttf",font_dir/"arialbd.ttf"),
             (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
              Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))]
regular,bold = "Helvetica","Helvetica-Bold"
for reg,b in font_pair:
    if reg.exists() and b.exists():
        pdfmetrics.registerFont(TTFont("ReportRegular",str(reg)))
        pdfmetrics.registerFont(TTFont("ReportBold",str(b)))
        regular,bold = "ReportRegular","ReportBold"
        break
styles={
    "title": ParagraphStyle("Title",fontName=bold,fontSize=22,leading=24,spaceAfter=11),
    "heading": ParagraphStyle("Heading",fontName=bold,fontSize=13,leading=16,spaceBefore=10,spaceAfter=5,keepWithNext=True),
    "body": ParagraphStyle("Body",fontName=regular,fontSize=10.1,leading=13.3,spaceAfter=8,alignment=TA_LEFT),
    "caption": ParagraphStyle("Caption",fontName=regular,fontSize=8.7,leading=11.5,spaceAfter=8,textColor=colors.HexColor("#374151")),
}
member_font = Path("C:/Windows/Fonts/Deng.ttf")
if not member_font.exists():
    member_font = Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
if member_font.exists():
    pdfmetrics.registerFont(TTFont("MemberNames", str(member_font)))
styles["member"] = ParagraphStyle("Member", parent=styles["body"],
                                  fontName="MemberNames" if member_font.exists() else regular,
                                  spaceAfter=2)
story=[]
lines=(root/"report_source.txt").read_text(encoding="utf-8-sig").splitlines()
for i,line in enumerate(lines):
    if line.startswith("# "):
        story.append(Paragraph(escape(line[2:]),styles["title"]))
    elif line.startswith("## "):
        story.append(Paragraph(escape(line[3:]),styles["heading"]))
    elif line.startswith("@member "):
        story.append(Paragraph(escape(line[8:]), styles["member"]))
    elif line=="@blindmap":
        figure = Image(str(root/"classroom_blind"/"figures"/"L3_map.png"))
        scale = min(310/figure.imageWidth, 255/figure.imageHeight)
        figure.drawWidth = scale*figure.imageWidth
        figure.drawHeight = scale*figure.imageHeight
        story.append(KeepTogether([figure, Paragraph(escape(lines[i+1]),styles["caption"])]))
    elif line=="@page":
        story.append(PageBreak())
    elif line.startswith("@figure "):
        story.append(KeepTogether([figures[line[8:]],Paragraph(escape(lines[i+1]),styles["caption"])]))
    elif line and not line.startswith("Figure "):
        story.append(Paragraph(line.replace("Ω/□","Ω/sq"),styles["body"]))

def footer(canvas,doc):
    canvas.setFont("Helvetica",8)
    canvas.setFillColor(colors.HexColor("#374151"))
    canvas.drawString(54,28,"QXU6028  |  G13")
    canvas.drawRightString(A4[0]-54,28,str(doc.page))

doc=SimpleDocTemplate(str(gen/"G13_report.pdf"),pagesize=A4,rightMargin=52,leftMargin=52,
                      topMargin=42,bottomMargin=42,title="Electrical Characterization of a Graphene on Sapphire Wafer")
doc.build(story,onFirstPage=footer,onLaterPages=footer)
