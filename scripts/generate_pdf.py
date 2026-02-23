#!/usr/bin/env python3
"""
generate_pdf.py — Convert exercises.ex → a beautifully formatted PDF.

Usage:
    python3 generate_pdf.py [exercises.ex] [output.pdf]

Defaults:
    input  = exercise_data/exercises.ex
    output = exercise_data/outputs/exercises.pdf
"""

import sys
import os
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    KeepTogether, PageBreak, HRFlowable,
    NextPageTemplate,
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ─── Font registration ───────────────────────────────────────────────────────
# DejaVu Sans: full Unicode coverage including Azerbaijani (ə Ə ğ ı ş ç ö ü …)

_FONT_DIR = Path(__file__).parent.parent / "fonts"

def _reg(name, filename):
    pdfmetrics.registerFont(TTFont(name, str(_FONT_DIR / filename)))

_reg("DejaVu",       "DejaVuSans.ttf")
_reg("DejaVu-Bold",  "DejaVuSans-Bold.ttf")
_reg("DejaVu-Italic","DejaVuSans-Oblique.ttf")
_reg("DejaVu-BoldItalic", "DejaVuSans-BoldOblique.ttf")

pdfmetrics.registerFontFamily(
    "DejaVu",
    normal     ="DejaVu",
    bold       ="DejaVu-Bold",
    italic     ="DejaVu-Italic",
    boldItalic ="DejaVu-BoldItalic",
)

# Convenience aliases so helper code stays readable
FONT_NORMAL = "DejaVu"
FONT_BOLD   = "DejaVu-Bold"
FONT_ITALIC = "DejaVu-Italic"
FONT_BOLDITALIC = "DejaVu-BoldItalic"

# ─── Colour palette ──────────────────────────────────────────────────────────

TEAL       = colors.HexColor("#2A7F7F")
TEAL_LIGHT = colors.HexColor("#D6EEEE")
GOLD       = colors.HexColor("#C9922A")
GOLD_LIGHT = colors.HexColor("#FDF3E3")
SLATE      = colors.HexColor("#3B4A5A")
SLATE_LIGHT= colors.HexColor("#EDF0F3")
WHITE      = colors.white
INK        = colors.HexColor("#1A1A2E")
MUTED      = colors.HexColor("#7A8A99")
ANSWER_BG  = colors.HexColor("#F0FAF0")
ANSWER_BORDER = colors.HexColor("#4CAF50")

# ─── Page geometry ───────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4
MARGIN_OUTER = 20 * mm
MARGIN_INNER = 20 * mm
MARGIN_TOP   = 28 * mm
MARGIN_BOT   = 28 * mm

# ─── Custom flowables ────────────────────────────────────────────────────────

class SideBar(Flowable):
    """A coloured left-side bar used as exercise header accent."""
    def __init__(self, width, height, colour=TEAL, radius=3):
        super().__init__()
        self.width  = width
        self.height = height
        self.colour = colour
        self.radius = radius

    def draw(self):
        self.canv.setFillColor(self.colour)
        self.canv.roundRect(0, 0, self.width, self.height,
                            self.radius, fill=1, stroke=0)


class AnswerBox(Flowable):
    """A small rounded rectangle for writing an answer in."""
    def __init__(self, w=60*mm, h=8*mm, label="", colour=TEAL):
        super().__init__()
        self.width  = w
        self.height = h
        self.label  = label
        self.colour = colour

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.colour)
        c.setFillColor(colors.HexColor("#F8FAFA"))
        c.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=1)
        if self.label:
            c.setFillColor(self.colour)
            c.setFont(FONT_NORMAL, 7)
            c.drawString(3, 2, self.label)


class Ornament(Flowable):
    """Decorative horizontal rule with a central diamond."""
    def __init__(self, width, colour=TEAL, thin=0.6):
        super().__init__()
        self.width  = width
        self.height = 6
        self.colour = colour
        self.thin   = thin

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.colour)
        c.setLineWidth(self.thin)
        mid = self.height / 2
        gap = 6
        c.line(0, mid, self.width / 2 - gap, mid)
        c.line(self.width / 2 + gap, mid, self.width, mid)
        # diamond
        c.setFillColor(self.colour)
        pts = [
            self.width/2, mid + 4,
            self.width/2 + 4, mid,
            self.width/2, mid - 4,
            self.width/2 - 4, mid,
        ]
        p = c.beginPath()
        p.moveTo(pts[0], pts[1])
        for i in range(2, len(pts), 2):
            p.lineTo(pts[i], pts[i+1])
        p.close()
        c.drawPath(p, fill=1, stroke=0)


# ─── Page templates (decorative backgrounds) ─────────────────────────────────

def _draw_exercise_page(canv, doc):
    """Background for exercise pages: top teal band + subtle corner accents."""
    canv.saveState()

    # Top teal header band
    band_h = 14 * mm
    canv.setFillColor(TEAL)
    canv.rect(0, PAGE_H - band_h, PAGE_W, band_h, fill=1, stroke=0)

    # Book title in header band
    canv.setFillColor(WHITE)
    canv.setFont(FONT_BOLD, 9)
    canv.drawString(MARGIN_OUTER, PAGE_H - band_h + 5*mm, "Azərbaycanca — Exercises")

    # Page number (right side of header band)
    canv.setFont(FONT_NORMAL, 8)
    pg = str(doc.page)
    canv.drawRightString(PAGE_W - MARGIN_OUTER, PAGE_H - band_h + 5*mm, pg)

    # Bottom gold thin rule
    canv.setStrokeColor(GOLD)
    canv.setLineWidth(1.2)
    canv.line(MARGIN_OUTER, MARGIN_BOT - 6*mm,
              PAGE_W - MARGIN_OUTER, MARGIN_BOT - 6*mm)

    # Bottom footer text
    canv.setFillColor(MUTED)
    canv.setFont(FONT_ITALIC, 7.5)
    canv.drawCentredString(PAGE_W / 2, MARGIN_BOT - 11*mm,
                           "Azerbaijani Language Learning Programme")

    # Subtle corner triangles (top-left, bottom-right)
    canv.setFillColor(GOLD)
    size = 18 * mm
    # bottom-right
    p = canv.beginPath()
    p.moveTo(PAGE_W, 0)
    p.lineTo(PAGE_W - size, 0)
    p.lineTo(PAGE_W, size)
    p.close()
    canv.drawPath(p, fill=1, stroke=0)

    canv.restoreState()


def _draw_answer_page(canv, doc):
    """Background for answer-sheet pages: gold header band."""
    canv.saveState()

    band_h = 14 * mm
    canv.setFillColor(GOLD)
    canv.rect(0, PAGE_H - band_h, PAGE_W, band_h, fill=1, stroke=0)

    canv.setFillColor(WHITE)
    canv.setFont(FONT_BOLD, 9)
    canv.drawString(MARGIN_OUTER, PAGE_H - band_h + 5*mm, "Answer Key")

    canv.setFont(FONT_NORMAL, 8)
    canv.drawRightString(PAGE_W - MARGIN_OUTER,
                         PAGE_H - band_h + 5*mm, str(doc.page))

    canv.setStrokeColor(TEAL)
    canv.setLineWidth(1.2)
    canv.line(MARGIN_OUTER, MARGIN_BOT - 6*mm,
              PAGE_W - MARGIN_OUTER, MARGIN_BOT - 6*mm)

    canv.setFillColor(MUTED)
    canv.setFont(FONT_ITALIC, 7.5)
    canv.drawCentredString(PAGE_W / 2, MARGIN_BOT - 11*mm,
                           "Azerbaijani Language Learning Programme")

    # Corner accent — teal this time
    canv.setFillColor(TEAL)
    size = 18 * mm
    p = canv.beginPath()
    p.moveTo(PAGE_W, 0)
    p.lineTo(PAGE_W - size, 0)
    p.lineTo(PAGE_W, size)
    p.close()
    canv.drawPath(p, fill=1, stroke=0)

    canv.restoreState()


# ─── .ex parser ──────────────────────────────────────────────────────────────

def parse_ex_file(path: Path) -> dict:
    """
    Parse exercises.ex into a structured dict:

    {
        "meta": {"date": ..., "total": ...},
        "exercises": [
            {
                "num": 1,
                "label": "...",
                "type": "...",
                "tags": "...",
                "count": 5,
                "introduces": "...",   # optional
                "items": [
                    {"id": "1.1", "az": ..., "en": ...},          # translation
                    {"id": "2.1", "sentence": ..., "answer": ..., "explanation": ..., "suffix_type": ...},
                    {"id": "3.1", "sentence": ..., "A": ..., "B":..., "C":..., "D":..., "answer":..., "explanation":...},
                ]
            },
            ...
        ]
    }
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    result = {"meta": {}, "exercises": []}
    current_exercise = None
    current_item     = None

    def flush_item():
        if current_item and current_exercise is not None:
            result["exercises"][current_exercise]["items"].append(current_item)

    ex_idx  = -1   # index into result["exercises"]

    for raw in lines:
        line = raw.strip()

        # Skip comment lines (but harvest meta)
        if line.startswith("#"):
            m = re.match(r"#\s*Date:\s*(.+)", line)
            if m:
                result["meta"]["date"] = m.group(1).strip()
            m = re.match(r"#\s*Total exercises:\s*(\d+)", line)
            if m:
                result["meta"]["total"] = int(m.group(1))
            continue

        # New exercise block
        m = re.match(r"\[exercise:(\d+)\]", line)
        if m:
            flush_item()
            current_item = None
            ex = {
                "num":        int(m.group(1)),
                "label":      "",
                "type":       "",
                "tags":       "",
                "count":      0,
                "introduces": None,
                "items":      [],
            }
            result["exercises"].append(ex)
            ex_idx = len(result["exercises"]) - 1
            current_exercise = ex_idx
            continue

        # New item block
        m = re.match(r"\[item:(\d+\.\w+)\]", line)
        if m:
            flush_item()
            current_item = {"id": m.group(1)}
            continue

        # Key: value pairs
        if ":" in line and not line.startswith("["):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()

            if current_item is not None:
                current_item[key] = val
            elif current_exercise is not None:
                ex = result["exercises"][current_exercise]
                if key == "label":
                    ex["label"] = val
                elif key == "type":
                    ex["type"] = val
                elif key == "tags":
                    ex["tags"] = val
                elif key == "count":
                    ex["count"] = int(val)
                elif key == "introduces":
                    ex["introduces"] = val

    flush_item()
    return result


# ─── Style definitions ────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()

    def s(name, **kw):
        return ParagraphStyle(name, **kw)

    styles = {}

    # Cover / section titles
    styles["cover_title"] = s("cover_title",
        fontName=FONT_BOLD, fontSize=28, leading=34,
        textColor=TEAL, alignment=TA_CENTER, spaceAfter=4*mm)

    styles["cover_sub"] = s("cover_sub",
        fontName=FONT_ITALIC, fontSize=13, leading=18,
        textColor=GOLD, alignment=TA_CENTER, spaceAfter=2*mm)

    styles["cover_meta"] = s("cover_meta",
        fontName=FONT_NORMAL, fontSize=9, leading=13,
        textColor=MUTED, alignment=TA_CENTER, spaceAfter=1*mm)

    # Exercise header
    styles["ex_number"] = s("ex_number",
        fontName=FONT_BOLD, fontSize=9, leading=12,
        textColor=WHITE)

    styles["ex_label"] = s("ex_label",
        fontName=FONT_BOLD, fontSize=14, leading=18,
        textColor=SLATE, spaceAfter=1*mm)

    styles["ex_meta"] = s("ex_meta",
        fontName=FONT_ITALIC, fontSize=8, leading=11,
        textColor=MUTED, spaceAfter=3*mm)

    styles["introduces"] = s("introduces",
        fontName=FONT_ITALIC, fontSize=8.5, leading=12,
        textColor=GOLD, spaceAfter=2*mm)

    # Item numbering
    styles["item_num"] = s("item_num",
        fontName=FONT_BOLD, fontSize=9, leading=12,
        textColor=TEAL)

    # Body text
    styles["body"] = s("body",
        fontName=FONT_NORMAL, fontSize=10.5, leading=15,
        textColor=INK, spaceAfter=1.5*mm)

    styles["body_az"] = s("body_az",
        fontName=FONT_BOLD, fontSize=11, leading=16,
        textColor=SLATE, spaceAfter=0.5*mm)

    styles["body_en"] = s("body_en",
        fontName=FONT_ITALIC, fontSize=10, leading=14,
        textColor=MUTED, spaceAfter=1*mm)

    styles["sentence"] = s("sentence",
        fontName=FONT_NORMAL, fontSize=11, leading=16,
        textColor=INK, spaceAfter=1*mm)

    styles["suffix_hint"] = s("suffix_hint",
        fontName=FONT_ITALIC, fontSize=8.5, leading=12,
        textColor=MUTED, spaceAfter=0.5*mm)

    styles["abcd_option"] = s("abcd_option",
        fontName=FONT_NORMAL, fontSize=10.5, leading=14,
        textColor=INK)

    styles["explanation"] = s("explanation",
        fontName=FONT_ITALIC, fontSize=8.5, leading=12,
        textColor=MUTED, spaceAfter=1*mm)

    # Answer sheet
    styles["ans_header"] = s("ans_header",
        fontName=FONT_BOLD, fontSize=18, leading=24,
        textColor=GOLD, alignment=TA_CENTER, spaceAfter=4*mm)

    styles["ans_ex_label"] = s("ans_ex_label",
        fontName=FONT_BOLD, fontSize=11, leading=15,
        textColor=TEAL, spaceAfter=1*mm)

    styles["ans_item_id"] = s("ans_item_id",
        fontName=FONT_BOLD, fontSize=9, leading=12,
        textColor=SLATE)

    styles["ans_answer"] = s("ans_answer",
        fontName=FONT_BOLD, fontSize=10, leading=14,
        textColor=INK)

    styles["ans_explanation"] = s("ans_explanation",
        fontName=FONT_NORMAL, fontSize=8.5, leading=12,
        textColor=MUTED)

    return styles


# ─── Flowable builders ────────────────────────────────────────────────────────

CONTENT_W = PAGE_W - MARGIN_OUTER - MARGIN_INNER   # usable content width

def exercise_header(ex: dict, styles: dict) -> list:
    """Returns a list of flowables for the exercise header block."""
    num   = ex["num"]
    label = ex["label"] or f"Exercise {num}"
    type_ = ex["type"]
    tags  = ex.get("tags", "")
    intro = ex.get("introduces")

    TYPE_LABELS = {
        "translation_az_en": "Azerbaijani → English",
        "translation_en_az": "English → Azerbaijani",
        "correct_suffix":    "Supply the Correct Suffix",
        "abcd_gap_fill":     "Multiple Choice — Fill in the Gap",
    }
    type_display = TYPE_LABELS.get(type_, type_)

    # Number badge + label in a table
    badge_w  = 22 * mm
    label_w  = CONTENT_W - badge_w - 4 * mm

    badge_data = [[Paragraph(f"<b>№&nbsp;{num}</b>", styles["ex_number"])]]
    badge_table = Table(badge_data, colWidths=[badge_w])
    badge_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), TEAL),
        ("ROUNDEDCORNERS", [4]),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))

    header_data = [[badge_table, Paragraph(label, styles["ex_label"])]]
    header_table = Table(header_data, colWidths=[badge_w + 4*mm, label_w])
    header_table.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))

    elems = [header_table, Spacer(1, 2*mm)]

    # Type + tags line
    meta_text = f"<i>{type_display}</i>"
    if tags:
        short_tags = [t.strip().replace("vocab:", "").replace("grammar:", "")
                      for t in tags.split(",")]
        tag_str = " · ".join(short_tags[:5])
        if len(short_tags) > 5:
            tag_str += " …"
        meta_text += f"  <font color='#{MUTED.hexval()[2:]}'>| {tag_str}</font>"
    elems.append(Paragraph(meta_text, styles["ex_meta"]))

    if intro:
        elems.append(Paragraph(f"★ New word introduced: <b>{intro}</b>",
                                styles["introduces"]))

    elems.append(HRFlowable(width="100%", thickness=1,
                             color=TEAL_LIGHT, spaceAfter=3*mm))
    return elems


def translation_items(items: list, ex_type: str, styles: dict) -> list:
    """Flowables for translation_az_en / translation_en_az items."""
    elems = []
    for item in items:
        iid = item.get("id", "")
        az  = item.get("az", "")
        en  = item.get("en", "")

        if ex_type == "translation_en_az":
            question = en
            q_style  = styles["body"]
            blank    = AnswerBox(w=CONTENT_W, h=22*mm)
        else:
            question = az
            q_style  = styles["body_az"]
            blank    = AnswerBox(w=CONTENT_W, h=22*mm)

        num_cell = Paragraph(f"<b>{iid}</b>", styles["item_num"])
        q_cell   = Paragraph(question, q_style)

        row = Table([[num_cell, q_cell]],
                    colWidths=[14*mm, CONTENT_W - 14*mm])
        row.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 2),
        ]))

        block = [row, blank, Spacer(1, 4*mm)]
        elems.append(KeepTogether(block))

    return elems


def suffix_items(items: list, styles: dict) -> list:
    """Flowables for correct_suffix items."""
    elems = []
    for item in items:
        iid         = item.get("id", "")
        sentence    = item.get("sentence", "")
        suffix_type = item.get("suffix_type", "")

        # Highlight the blank (___) in gold
        sentence_html = sentence.replace("___",
            f'<font color="#{GOLD.hexval()[2:]}"><b>_______</b></font>')

        num_p  = Paragraph(f"<b>{iid}</b>", styles["item_num"])
        sent_p = Paragraph(sentence_html, styles["sentence"])
        blank  = AnswerBox(w=80*mm, h=14*mm, label="answer:")

        row = Table([[num_p, [sent_p, blank]]],
                    colWidths=[14*mm, CONTENT_W - 14*mm])
        row.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 2),
        ]))

        elems.append(KeepTogether([row, Spacer(1, 4*mm)]))

    return elems


def abcd_items(items: list, styles: dict) -> list:
    """Flowables for abcd_gap_fill items."""
    elems = []
    for item in items:
        iid      = item.get("id", "")
        sentence = item.get("sentence", "")
        opts     = {k: item.get(k, "") for k in ("A", "B", "C", "D")}

        sentence_html = sentence.replace("_____",
            f'<font color="#{TEAL.hexval()[2:]}"><b>_______</b></font>')

        num_p  = Paragraph(f"<b>{iid}</b>", styles["item_num"])
        sent_p = Paragraph(sentence_html, styles["sentence"])

        # Two-column option grid
        opt_rows = []
        keys = ["A", "B", "C", "D"]
        for i in range(0, 4, 2):
            ka, kb = keys[i], keys[i+1]
            cell_a = Paragraph(f"<b>{ka})</b>  {opts[ka]}", styles["abcd_option"])
            cell_b = Paragraph(f"<b>{kb})</b>  {opts[kb]}", styles["abcd_option"])
            opt_rows.append([cell_a, cell_b])

        opt_table = Table(opt_rows,
                          colWidths=[(CONTENT_W - 14*mm) / 2] * 2)
        opt_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), SLATE_LIGHT),
            ("ROUNDEDCORNERS",[4]),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
            ("RIGHTPADDING",  (0,0), (-1,-1), 6),
            ("LINEBELOW",     (0,0), (-1,-2), 0.4, MUTED),
            ("ROWBACKGROUNDS",(0,0), (-1,-1),
             [SLATE_LIGHT, colors.HexColor("#E8ECF0")]),
        ]))

        row = Table([[num_p, [sent_p, Spacer(1, 2*mm), opt_table]]],
                    colWidths=[14*mm, CONTENT_W - 14*mm])
        row.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ]))

        elems.append(KeepTogether([row, Spacer(1, 5*mm)]))

    return elems


# ─── Answer sheet ────────────────────────────────────────────────────────────

def answer_sheet(data: dict, styles: dict) -> list:
    """All flowables for the answer-key section (starts on a new page)."""
    elems = [
        NextPageTemplate("answer"),
        PageBreak(),
        Spacer(1, 4*mm),
        Paragraph("Answer Key", styles["ans_header"]),
        Ornament(CONTENT_W, colour=GOLD),
        Spacer(1, 6*mm),
    ]

    for ex in data["exercises"]:
        ex_num  = ex["num"]
        ex_label = ex["label"] or f"Exercise {ex_num}"
        ex_type  = ex["type"]

        elems.append(Paragraph(f"Exercise {ex_num} — {ex_label}",
                               styles["ans_ex_label"]))
        elems.append(HRFlowable(width="100%", thickness=0.6,
                                color=GOLD_LIGHT, spaceAfter=2*mm))

        # Build rows for each item
        rows = []
        for item in ex["items"]:
            iid    = item.get("id", "")
            answer = item.get("answer", "")
            expl   = item.get("explanation", "")

            if ex_type in ("translation_az_en", "translation_en_az"):
                az = item.get("az", "")
                en = item.get("en", "")
                answer_text = en if ex_type == "translation_az_en" else az
                expl_text   = az if ex_type == "translation_az_en" else en
            elif ex_type == "correct_suffix":
                answer_text = answer
                expl_text   = expl
            else:  # abcd
                letter = answer
                word   = item.get(letter, "")
                answer_text = f"{letter}) {word}"
                expl_text   = expl

            id_p  = Paragraph(f"<b>{iid}</b>", styles["ans_item_id"])
            ans_p = Paragraph(answer_text, styles["ans_answer"])
            expl_p= Paragraph(expl_text,   styles["ans_explanation"])

            col_w   = (CONTENT_W - 20*mm) / 2
            ans_row = Table([[id_p, ans_p, expl_p]],
                            colWidths=[16*mm, col_w * 0.6, col_w * 1.4 + 4*mm])
            ans_row.setStyle(TableStyle([
                ("VALIGN",       (0,0), (-1,-1), "TOP"),
                ("LEFTPADDING",  (0,0), (-1,-1), 4),
                ("RIGHTPADDING", (0,0), (-1,-1), 4),
                ("TOPPADDING",   (0,0), (-1,-1), 3),
                ("BOTTOMPADDING",(0,0), (-1,-1), 3),
                ("BACKGROUND",   (0,0), (-1,-1), ANSWER_BG),
                ("LINEBELOW",    (0,0), (-1,-1), 0.4,
                 colors.HexColor("#C8E6C9")),
            ]))
            rows.append(KeepTogether([ans_row, Spacer(1, 1*mm)]))

        elems.extend(rows)
        elems.append(Spacer(1, 6*mm))

    return elems


# ─── Cover page ──────────────────────────────────────────────────────────────

def cover_page(data: dict, styles: dict) -> list:
    """Decorative cover page flowables (uses exercise page template)."""
    meta  = data.get("meta", {})
    date  = meta.get("date", "")
    total = meta.get("total", len(data["exercises"]))
    n_ex  = len(data["exercises"])

    elems = []
    elems.append(Spacer(1, 30*mm))
    elems.append(Ornament(CONTENT_W, colour=TEAL))
    elems.append(Spacer(1, 8*mm))

    elems.append(Paragraph("Azərbaycanca", styles["cover_title"]))
    elems.append(Paragraph("Exercise Booklet", styles["cover_sub"]))
    elems.append(Spacer(1, 6*mm))
    elems.append(Ornament(CONTENT_W, colour=GOLD))
    elems.append(Spacer(1, 12*mm))

    if date:
        elems.append(Paragraph(f"Date: {date}", styles["cover_meta"]))
    elems.append(Paragraph(f"Exercises: {n_ex}  ·  Items: {total}",
                            styles["cover_meta"]))
    elems.append(Spacer(1, 20*mm))

    # Summary table of exercises
    rows = [["#", "Type", "Items"]]
    TYPE_SHORT = {
        "translation_az_en": "Az → En Translation",
        "translation_en_az": "En → Az Translation",
        "correct_suffix":    "Correct Suffix",
        "abcd_gap_fill":     "Multiple Choice",
    }
    for ex in data["exercises"]:
        rows.append([
            str(ex["num"]),
            TYPE_SHORT.get(ex["type"], ex["type"]),
            str(ex["count"]),
        ])

    tbl = Table(rows, colWidths=[14*mm, CONTENT_W - 40*mm, 22*mm])
    tbl.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",    (0,0), (-1,0), TEAL),
        ("TEXTCOLOR",     (0,0), (-1,0), WHITE),
        ("FONTNAME",      (0,0), (-1,0), FONT_BOLD),
        ("FONTSIZE",      (0,0), (-1,0), 9),
        ("TOPPADDING",    (0,0), (-1,0), 5),
        ("BOTTOMPADDING", (0,0), (-1,0), 5),
        # Body rows
        ("FONTNAME",      (0,1), (-1,-1), FONT_NORMAL),
        ("FONTSIZE",      (0,1), (-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, TEAL_LIGHT]),
        ("TOPPADDING",    (0,1), (-1,-1), 4),
        ("BOTTOMPADDING", (0,1), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#C0CDD8")),
        ("ALIGN",         (0,0), (0,-1), "CENTER"),
        ("ALIGN",         (2,0), (2,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))

    elems.append(tbl)
    elems.append(PageBreak())
    return elems


# ─── Main build ──────────────────────────────────────────────────────────────

def build_pdf(data: dict, out_path: Path):
    styles = build_styles()

    # Two frames — same geometry, different page backgrounds
    frame = Frame(
        MARGIN_OUTER, MARGIN_BOT,
        CONTENT_W,
        PAGE_H - MARGIN_TOP - MARGIN_BOT,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
        id="main",
    )

    exercise_tpl = PageTemplate(
        id="exercise",
        frames=[frame],
        onPage=_draw_exercise_page,
    )
    answer_tpl = PageTemplate(
        id="answer",
        frames=[frame],
        onPage=_draw_answer_page,
    )

    doc = BaseDocTemplate(
        str(out_path),
        pagesize=A4,
        pageTemplates=[exercise_tpl, answer_tpl],
        leftMargin=MARGIN_OUTER,
        rightMargin=MARGIN_INNER,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOT,
        title="Azərbaycanca — Exercise Booklet",
        author="Azerbaijani Language Learning Programme",
    )

    story = []

    # ── Cover ──
    story.extend(cover_page(data, styles))

    # ── Exercise pages ──
    for ex in data["exercises"]:
        ex_type = ex["type"]
        items   = ex["items"]

        # Header block
        hdr = exercise_header(ex, styles)
        story.extend(hdr)

        # Item blocks
        if ex_type in ("translation_az_en", "translation_en_az"):
            story.extend(translation_items(items, ex_type, styles))
        elif ex_type == "correct_suffix":
            story.extend(suffix_items(items, styles))
        elif ex_type == "abcd_gap_fill":
            story.extend(abcd_items(items, styles))

        story.append(Spacer(1, 6*mm))
        story.append(Ornament(CONTENT_W, colour=TEAL_LIGHT))
        story.append(Spacer(1, 4*mm))

    # ── Answer sheet ──
    story.extend(answer_sheet(data, styles))

    doc.build(story)


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    base     = Path(__file__).parent.parent / "exercise_data"
    out_base = base / "outputs"
    in_path  = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "exercises.ex"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else out_base / "exercises.pdf"
    out_base.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        print(f"ERROR: input file not found: {in_path}")
        sys.exit(1)

    print(f"Parsing  {in_path}")
    data = parse_ex_file(in_path)
    n_ex  = len(data["exercises"])
    n_it  = sum(len(e["items"]) for e in data["exercises"])
    print(f"Found {n_ex} exercise(s), {n_it} item(s)")

    print(f"Building {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_pdf(data, out_path)
    print(f"Done — {out_path}")


if __name__ == "__main__":
    main()
