#!/usr/bin/env python3
"""
generate_pdf.py — Convert exercises.ex → a formatted PDF.

Usage:
    python3 generate_pdf.py [exercises.ex] [output.pdf]

Defaults:
    input  = exercise_data/outputs/exercises.ex
    output = exercise_data/outputs/exercises.pdf
"""

import sys
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    KeepTogether, PageBreak, HRFlowable,
    NextPageTemplate, Image,
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ─── Fonts ───────────────────────────────────────────────────────────────────

_FONT_DIR  = Path(__file__).parent.parent / "fonts"
_LOGO_PATH = Path(__file__).parent.parent / "images" / "logo.png"

def _reg(name, path):
    pdfmetrics.registerFont(TTFont(name, str(_FONT_DIR / path)))

_reg("Mono",       "DejaVuSansMono.ttf")
_reg("Mono-Bold",  "DejaVuSansMono-Bold.ttf")
_reg("Mono-Ital",  "DejaVuSansMono-Oblique.ttf")
_reg("Mono-BoldI", "DejaVuSansMono-BoldOblique.ttf")

pdfmetrics.registerFontFamily(
    "Mono",
    normal="Mono", bold="Mono-Bold",
    italic="Mono-Ital", boldItalic="Mono-BoldI",
)

F  = "Mono"
FB = "Mono-Bold"
FI = "Mono-Ital"

# ─── Colours ─────────────────────────────────────────────────────────────────
# White BG + terminal green.  Toned down so it prints cleanly.

WHITE      = colors.HexColor("#FFFFFF")
BG         = colors.HexColor("#FAFAFA")    # page / box tint
INK        = colors.HexColor("#111111")    # main text
GREEN      = colors.HexColor("#1A6B1A")    # primary accent
GREEN2     = colors.HexColor("#2E9E2E")    # brighter green (secondary)
GREEN_PALE = colors.HexColor("#EBF5EB")    # answer-box fill
RULE       = colors.HexColor("#BBBBBB")    # light rules
GREY       = colors.HexColor("#666666")    # captions / muted
GREY_LIGHT = colors.HexColor("#EEEEEE")    # table alt-row

# ─── Page geometry ───────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4
ML = 22 * mm   # left margin
MR = 22 * mm   # right margin
MT = 26 * mm   # top margin
MB = 22 * mm   # bottom margin
CW = PAGE_W - ML - MR   # content width

# ─── Ornament ────────────────────────────────────────────────────────────────

class Ornament(Flowable):
    """Simple dashed separator — keeps the terminal-doc feel."""
    def __init__(self, width, colour=RULE, dash=None):
        super().__init__()
        self.width  = width
        self.height = 4
        self.colour = colour
        self.dash   = dash or [2, 3]

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.colour)
        c.setLineWidth(0.5)
        c.setDash(self.dash)
        c.line(0, 2, self.width, 2)
        c.setDash()   # reset


class AnswerRule(Flowable):
    """A single underline for writing an answer — minimal, printable."""
    def __init__(self, w=None, colour=GREEN):
        super().__init__()
        self.width  = w or CW
        self.height = 9   # pts
        self.colour = colour

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.colour)
        c.setLineWidth(0.8)
        c.line(0, 0, self.width, 0)


# ─── Page templates ───────────────────────────────────────────────────────────

def _header_footer(canv, doc, label_right=""):
    """Shared header/footer for all page templates."""
    canv.saveState()

    # ── Header ──
    y_head = PAGE_H - MT + 6 * mm

    # Left: "bəbir // azərbaycanca exercises"
    prefix = "bəbir //  "
    canv.setFont(FB, 7.5)
    canv.setFillColor(GREEN)
    canv.drawString(ML, y_head, prefix)
    prefix_w = pdfmetrics.stringWidth(prefix, FB, 7.5)
    canv.setFont(F, 7.5)
    canv.setFillColor(GREY)
    canv.drawString(ML + prefix_w, y_head, "azərbaycanca exercises")

    # Header rule
    canv.setStrokeColor(GREEN)
    canv.setLineWidth(0.6)
    canv.line(ML, y_head - 2.5*mm, PAGE_W - MR, y_head - 2.5*mm)

    # ── Footer ──
    y_foot = MB - 6 * mm
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.4)
    canv.line(ML, y_foot + 3*mm, PAGE_W - MR, y_foot + 3*mm)

    canv.setFont(F, 7)
    canv.setFillColor(GREY)
    if label_right:
        canv.drawString(ML, y_foot, label_right)
    canv.drawRightString(PAGE_W - MR, y_foot, f"[ {doc.page} ]")

    canv.restoreState()


def _draw_exercise_page(canv, doc):
    canv.saveState()
    canv.setFillColor(WHITE)
    canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canv.restoreState()
    _header_footer(canv, doc, label_right="")


def _draw_answer_page(canv, doc):
    canv.saveState()
    canv.setFillColor(WHITE)
    canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canv.restoreState()
    _header_footer(canv, doc, label_right="// answer key")


# ─── Parser ───────────────────────────────────────────────────────────────────

def parse_ex_file(path: Path) -> dict:
    text  = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    result = {"meta": {}, "exercises": []}
    cur_ex   = None
    cur_item = None
    ex_idx   = -1

    def flush():
        if cur_item is not None and cur_ex is not None:
            result["exercises"][cur_ex]["items"].append(cur_item)

    for raw in lines:
        line = raw.strip()

        if line.startswith("#"):
            m = re.match(r"#\s*Date:\s*(.+)", line)
            if m: result["meta"]["date"] = m.group(1).strip()
            m = re.match(r"#\s*Total exercises:\s*(\d+)", line)
            if m: result["meta"]["total"] = int(m.group(1))
            continue

        m = re.match(r"\[exercise:(\d+)\]", line)
        if m:
            flush(); cur_item = None
            ex = {"num": int(m.group(1)), "label": "", "type": "",
                  "tags": "", "count": 0, "introduces": None, "items": []}
            result["exercises"].append(ex)
            ex_idx = len(result["exercises"]) - 1
            cur_ex = ex_idx
            continue

        m = re.match(r"\[item:(\d+\.\w+)\]", line)
        if m:
            flush(); cur_item = {"id": m.group(1)}
            continue

        if ":" in line and not line.startswith("["):
            key, _, val = line.partition(":")
            key = key.strip(); val = val.strip()
            if cur_item is not None:
                cur_item[key] = val
            elif cur_ex is not None:
                ex = result["exercises"][cur_ex]
                if key == "label":      ex["label"]      = val
                elif key == "type":     ex["type"]       = val
                elif key == "tags":     ex["tags"]       = val
                elif key == "count":    ex["count"]      = int(val)
                elif key == "introduces": ex["introduces"] = val

    flush()
    return result


# ─── Styles ───────────────────────────────────────────────────────────────────

def build_styles():
    def s(name, **kw):
        kw.setdefault("fontName", F)
        return ParagraphStyle(name, **kw)

    return {
        # Cover
        "cover_title": s("cover_title",
            fontName=FB, fontSize=20, leading=24,
            textColor=INK, alignment=TA_CENTER, spaceAfter=2*mm),
        "cover_sub": s("cover_sub",
            fontName=FI, fontSize=9, leading=13,
            textColor=GREEN, alignment=TA_CENTER, spaceAfter=1*mm),
        "cover_meta": s("cover_meta",
            fontSize=8, leading=12,
            textColor=GREY, alignment=TA_CENTER, spaceAfter=0.5*mm),

        # Exercise header
        "ex_tag": s("ex_tag",
            fontName=FB, fontSize=8, leading=11, textColor=WHITE),
        "ex_label": s("ex_label",
            fontName=FB, fontSize=11, leading=14,
            textColor=INK, spaceAfter=1*mm),
        "ex_meta": s("ex_meta",
            fontName=FI, fontSize=7.5, leading=10,
            textColor=GREY, spaceAfter=1*mm),
        "introduces": s("introduces",
            fontName=FI, fontSize=7.5, leading=10,
            textColor=GREEN, spaceAfter=2*mm),

        # Items
        "item_num": s("item_num",
            fontName=FB, fontSize=8, leading=11, textColor=GREEN),
        "body": s("body",
            fontSize=9, leading=13, textColor=INK, spaceAfter=1*mm),
        "body_bold": s("body_bold",
            fontName=FB, fontSize=9, leading=13, textColor=INK, spaceAfter=1*mm),
        "sentence": s("sentence",
            fontSize=9.5, leading=14, textColor=INK, spaceAfter=1*mm),
        "abcd_option": s("abcd_option",
            fontSize=9, leading=12, textColor=INK),
        "explanation": s("explanation",
            fontName=FI, fontSize=7.5, leading=10,
            textColor=GREY, spaceAfter=0.5*mm),

        # Answer sheet
        "ans_header": s("ans_header",
            fontName=FB, fontSize=14, leading=18,
            textColor=INK, alignment=TA_CENTER, spaceAfter=3*mm),
        "ans_ex_label": s("ans_ex_label",
            fontName=FB, fontSize=9, leading=12,
            textColor=GREEN, spaceAfter=1*mm),
        "ans_item_id": s("ans_item_id",
            fontName=FB, fontSize=8, leading=10, textColor=GREY),
        "ans_answer": s("ans_answer",
            fontName=FB, fontSize=8.5, leading=11, textColor=INK),
        "ans_expl": s("ans_expl",
            fontName=FI, fontSize=7.5, leading=10, textColor=GREY),
    }


# ─── Flowable builders ────────────────────────────────────────────────────────

def exercise_header(ex, styles):
    num   = ex["num"]
    label = ex["label"] or f"Exercise {num}"
    type_ = ex["type"]
    tags  = ex.get("tags", "")
    intro = ex.get("introduces")

    TYPE_LABELS = {
        "translation_az_en": "az -> en",
        "translation_en_az": "en -> az",
        "correct_suffix":    "correct suffix",
        "abcd_gap_fill":     "multiple choice",
    }
    type_str = TYPE_LABELS.get(type_, type_)

    # `[ 01 ]` badge + label side by side
    badge_w = 18 * mm
    tag_p   = Paragraph(f"[ {num:02d} ]", styles["ex_tag"])
    badge   = Table([[tag_p]], colWidths=[badge_w])
    badge.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), GREEN),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))

    header_row = Table(
        [[badge, Paragraph(label, styles["ex_label"])]],
        colWidths=[badge_w + 3*mm, CW - badge_w - 3*mm],
    )
    header_row.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))

    elems = [header_row, Spacer(1, 1.5*mm)]

    # type + tags line
    meta = f"// {type_str}"
    if tags:
        parts = [t.strip().replace("vocab:","").replace("grammar:","")
                 for t in tags.split(",")]
        meta += "  |  " + "  ·  ".join(parts[:4])
        if len(parts) > 4:
            meta += " ..."
    elems.append(Paragraph(meta, styles["ex_meta"]))

    if intro:
        elems.append(Paragraph(f">> new word: {intro}", styles["introduces"]))

    elems.append(HRFlowable(width="100%", thickness=0.4,
                             color=RULE, spaceAfter=3*mm))
    return elems


def translation_items(items, ex_type, styles):
    elems = []
    for item in items:
        iid = item.get("id","")
        az  = item.get("az","")
        en  = item.get("en","")
        q   = en if ex_type == "translation_en_az" else az
        st  = "body" if ex_type == "translation_en_az" else "body_bold"

        num_p = Paragraph(iid, styles["item_num"])
        q_p   = Paragraph(q, styles[st])
        rule  = AnswerRule(w=CW - 14*mm)

        row = Table([[num_p, [q_p, Spacer(1, 1.5*mm), rule]]],
                    colWidths=[14*mm, CW - 14*mm])
        row.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ]))
        elems.append(KeepTogether([row, Spacer(1, 4*mm)]))

    return elems


def suffix_items(items, styles):
    elems = []
    for item in items:
        iid      = item.get("id","")
        sentence = item.get("sentence","")

        sent_html = sentence.replace(
            "___", f'<font color="#{GREEN.hexval()[2:]}"><b>______</b></font>')

        num_p  = Paragraph(iid, styles["item_num"])
        sent_p = Paragraph(sent_html, styles["sentence"])

        row = Table([[num_p, sent_p]],
                    colWidths=[14*mm, CW - 14*mm])
        row.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ]))
        elems.append(KeepTogether([row, Spacer(1, 4*mm)]))

    return elems


def abcd_items(items, styles):
    elems = []
    for item in items:
        iid      = item.get("id","")
        sentence = item.get("sentence","")
        opts     = {k: item.get(k,"") for k in ("A","B","C","D")}

        sent_html = sentence.replace(
            "_____", f'<font color="#{GREEN.hexval()[2:]}"><b>_____</b></font>')

        num_p  = Paragraph(iid, styles["item_num"])
        sent_p = Paragraph(sent_html, styles["sentence"])

        opt_w = (CW - 14*mm) / 2
        opt_rows = []
        for i in range(0, 4, 2):
            ka, kb = ("A","B","C","D")[i], ("A","B","C","D")[i+1]
            opt_rows.append([
                Paragraph(f"{ka})  {opts[ka]}", styles["abcd_option"]),
                Paragraph(f"{kb})  {opts[kb]}", styles["abcd_option"]),
            ])

        opt_tbl = Table(opt_rows, colWidths=[opt_w, opt_w])
        opt_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), GREY_LIGHT),
            ("TOPPADDING",    (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
            ("RIGHTPADDING",  (0,0), (-1,-1), 5),
            ("LINEBELOW",     (0,0), (-1,-2), 0.3, RULE),
            ("LINEAFTER",     (0,0), (-2,-1), 0.3, RULE),
        ]))

        row = Table([[num_p, [sent_p, Spacer(1,1.5*mm), opt_tbl]]],
                    colWidths=[14*mm, CW - 14*mm])
        row.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ]))
        elems.append(KeepTogether([row, Spacer(1, 5*mm)]))

    return elems


# ─── Answer sheet ─────────────────────────────────────────────────────────────

def answer_sheet(data, styles):
    elems = [
        NextPageTemplate("answer"),
        PageBreak(),
        Spacer(1, 3*mm),
        Paragraph("// answer key", styles["ans_header"]),
        Ornament(CW, colour=GREEN),
        Spacer(1, 5*mm),
    ]

    for ex in data["exercises"]:
        ex_type = ex["type"]
        elems.append(Paragraph(
            f"[ {ex['num']:02d} ]  {ex['label']}", styles["ans_ex_label"]))
        elems.append(HRFlowable(width="100%", thickness=0.3,
                                color=RULE, spaceAfter=1.5*mm))

        for item in ex["items"]:
            iid    = item.get("id","")
            answer = item.get("answer","")
            expl   = item.get("explanation","")

            if ex_type in ("translation_az_en", "translation_en_az"):
                az = item.get("az","")
                en = item.get("en","")
                ans_text  = en if ex_type == "translation_az_en" else az
                expl_text = az if ex_type == "translation_az_en" else en
            elif ex_type == "correct_suffix":
                ans_text  = answer
                expl_text = expl
            else:
                letter    = answer
                ans_text  = f"{letter}) {item.get(letter,'')}"
                expl_text = expl

            col_w = (CW - 16*mm) / 2
            ans_row = Table(
                [[Paragraph(iid, styles["ans_item_id"]),
                  Paragraph(ans_text, styles["ans_answer"]),
                  Paragraph(expl_text, styles["ans_expl"])]],
                colWidths=[14*mm, col_w * 0.55, col_w * 1.45 + 2*mm],
            )
            ans_row.setStyle(TableStyle([
                ("VALIGN",       (0,0), (-1,-1), "TOP"),
                ("LEFTPADDING",  (0,0), (-1,-1), 3),
                ("RIGHTPADDING", (0,0), (-1,-1), 3),
                ("TOPPADDING",   (0,0), (-1,-1), 2),
                ("BOTTOMPADDING",(0,0), (-1,-1), 2),
                ("BACKGROUND",   (0,0), (-1,-1), GREEN_PALE),
                ("LINEBELOW",    (0,0), (-1,-1), 0.3, RULE),
            ]))
            elems.append(KeepTogether([ans_row, Spacer(1, 0.8*mm)]))

        elems.append(Spacer(1, 5*mm))

    return elems


# ─── Cover page ───────────────────────────────────────────────────────────────

def cover_page(data, styles):
    meta  = data.get("meta", {})
    date  = meta.get("date","")
    n_ex  = len(data["exercises"])
    total = meta.get("total", n_ex)

    elems = [Spacer(1, 10*mm)]

    # Logo — centred; the black box on white looks like a sticker/stamp
    if _LOGO_PATH.exists():
        logo_w = min(CW * 0.65, 100*mm)
        logo_h = logo_w * (9 / 16)
        img = Image(str(_LOGO_PATH), width=logo_w, height=logo_h)
        img.hAlign = "CENTER"
        elems.append(img)
        elems.append(Spacer(1, 6*mm))

    elems.append(Ornament(CW, colour=GREEN, dash=[4, 2]))
    elems.append(Spacer(1, 5*mm))

    elems.append(Paragraph("azərbaycanca", styles["cover_title"]))
    elems.append(Paragraph("exercise booklet", styles["cover_sub"]))
    elems.append(Spacer(1, 3*mm))
    elems.append(Ornament(CW, colour=RULE))
    elems.append(Spacer(1, 6*mm))

    if date:
        elems.append(Paragraph(f"generated: {date}", styles["cover_meta"]))
    elems.append(Paragraph(
        f"exercises: {n_ex}  //  items: {total}", styles["cover_meta"]))
    elems.append(Spacer(1, 8*mm))

    # Summary table
    rows = [["#", "type", "items"]]
    TYPE_SHORT = {
        "translation_az_en": "az -> en translation",
        "translation_en_az": "en -> az translation",
        "correct_suffix":    "correct suffix",
        "abcd_gap_fill":     "multiple choice",
    }
    for ex in data["exercises"]:
        rows.append([
            f"[{ex['num']:02d}]",
            TYPE_SHORT.get(ex["type"], ex["type"]),
            str(ex["count"]),
        ])

    tbl = Table(rows, colWidths=[14*mm, CW - 36*mm, 18*mm])
    tbl.setStyle(TableStyle([
        ("FONTNAME",      (0,0), (-1,-1), F),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
        ("FONTNAME",      (0,0), (-1,0),  FB),
        ("TEXTCOLOR",     (0,0), (-1,0),  WHITE),
        ("BACKGROUND",    (0,0), (-1,0),  GREEN),
        ("TEXTCOLOR",     (0,1), (-1,-1), INK),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, GREY_LIGHT]),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("GRID",          (0,0), (-1,-1), 0.3, RULE),
        ("ALIGN",         (0,0), (0,-1),  "CENTER"),
        ("ALIGN",         (2,0), (2,-1),  "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))

    elems.append(tbl)
    elems.append(PageBreak())
    return elems


# ─── Build PDF ────────────────────────────────────────────────────────────────

def build_pdf(data, out_path):
    styles = build_styles()

    frame = Frame(
        ML, MB, CW, PAGE_H - MT - MB,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
        id="main",
    )

    doc = BaseDocTemplate(
        str(out_path),
        pagesize=A4,
        pageTemplates=[
            PageTemplate(id="exercise", frames=[frame],
                         onPage=_draw_exercise_page),
            PageTemplate(id="answer",   frames=[frame],
                         onPage=_draw_answer_page),
        ],
        leftMargin=ML, rightMargin=MR,
        topMargin=MT,  bottomMargin=MB,
        title="azərbaycanca — exercise booklet",
        author="bəbir",
    )

    story = []
    story.extend(cover_page(data, styles))

    for ex in data["exercises"]:
        story.extend(exercise_header(ex, styles))

        t = ex["type"]
        if t in ("translation_az_en", "translation_en_az"):
            story.extend(translation_items(ex["items"], t, styles))
        elif t == "correct_suffix":
            story.extend(suffix_items(ex["items"], styles))
        elif t == "abcd_gap_fill":
            story.extend(abcd_items(ex["items"], styles))

        story.append(Spacer(1, 4*mm))
        story.append(Ornament(CW, colour=RULE))
        story.append(Spacer(1, 4*mm))

    story.extend(answer_sheet(data, styles))
    doc.build(story)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    base     = Path(__file__).parent.parent / "exercise_data"
    out_base = base / "outputs"
    in_path  = Path(sys.argv[1]) if len(sys.argv) > 1 else out_base / "exercises.ex"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else out_base / "exercises.pdf"
    out_base.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        print(f"ERROR: input file not found: {in_path}")
        sys.exit(1)

    print(f"parsing   {in_path}")
    data = parse_ex_file(in_path)
    n_ex = len(data["exercises"])
    n_it = sum(len(e["items"]) for e in data["exercises"])
    print(f"found     {n_ex} exercises, {n_it} items")

    print(f"building  {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_pdf(data, out_path)
    print(f"done  ->  {out_path}")


if __name__ == "__main__":
    main()
