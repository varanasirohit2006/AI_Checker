"""Generate synthetic integrity fixtures + ground-truth manifest (Step 6).

Run:  .venv/Scripts/python.exe tests/fixtures/make_fixtures.py
Outputs DOCX/PDF files and manifest.json in this directory. Deterministic.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from confusable_homoglyphs import confusables
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

WIDTH, HEIGHT = letter

HOMOGLYPH_WORDS = [
    "раypal", "gооgle", "аpple", "micrоsoft",
    "paypаl", "amazоn", "facebооk", "twittеr",
    "netflіx", "spotіfy", "linkеdIn", "instаgram",
]
ZW_CHARS = ["\u200b"] * 5 + ["\u200c"] * 2 + ["\u200d"] * 2 + \
           ["\u00ad"] * 3 + ["\ufeff"] * 1 + ["\u202e"] * 1 + ["\u2060"] * 1

RUSSIAN = ("Каждое утро я гуляю по набережной, даже зимой, когда ветер обжигает лицо. "
           "В это время город ещё спит, и только дворники шуршат метлами по асфальту. "
           "Однажды я встретил там старого рыбака, который сказал мне, что клёв зависит "
           "не от погоды, а от терпения.")
ENGLISH = ("The committee reviewed the proposal on a rainy Tuesday afternoon. "
           "Members raised concerns about the budget, the timeline, and the staffing plan. "
           "After a long discussion the chair called for a vote and the motion carried. "
           "Staff were asked to draft a revised schedule before the next meeting.")


def confusable_count(word):
    return sum(1 for info in confusables.is_confusable(word, preferred_aliases=["latin"])
               if confusables.alias(info["character"]) != "LATIN")


def shade(elm_pr, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    elm_pr.append(shd)


def add_run(paragraph, text, color=None, size=None, hidden=False, bold=False):
    run = paragraph.add_run(text)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    if size:
        run.font.size = Pt(size)
    if hidden:
        run.font.hidden = True
    run.bold = bold
    return run


def manifest_entry(file, category, kind, key, count, locator):
    return {"file": file, "category": category, "kind": kind,
            "key": key, "count": count, "locator": locator}


def make_docx_fixtures(manifest):
    # 1. homoglyphs
    doc = Document()
    for p in range(3):
        words = HOMOGLYPH_WORDS[p * 4:(p + 1) * 4]
        para = doc.add_paragraph("Please verify ")
        for i, w in enumerate(words):
            para.add_run(w)
            para.add_run(" and " if i < 3 else " before Friday.")
            manifest.append(manifest_entry(
                "tampered_homoglyphs.docx", "replaced_character", "mixed_script_word",
                w, confusable_count(w), {"paragraph": p}))
    doc.save(HERE / "tampered_homoglyphs.docx")

    # 2. zero-width characters
    doc = Document()
    base = "This ordinary sentence conceals invisible characters inside its words."
    for p in range(2):
        chars = ZW_CHARS[p * 8:(p + 1) * 8] if p == 0 else ZW_CHARS[8:]
        text = base
        for i, ch in enumerate(chars):
            pos = 5 + i * 7
            text = text[:pos] + ch + text[pos:]
        doc.add_paragraph(text)
        for ch in set(chars):
            manifest.append(manifest_entry(
                "tampered_zero_width.docx", "hidden_unicode", "invisible_character",
                f"U+{ord(ch):04X}", chars.count(ch), {"paragraph": p}))
    doc.save(HERE / "tampered_zero_width.docx")

    # 3. hidden text runs (white / microscopic / vanish)
    spec = [
        (0, "hidden invoice details", "white_font", {"color": "FFFFFF"}),
        (1, "secret keyword", "white_font", {"color": "F5F5F5"}),
        (2, "microscopic note one", "microscopic_font", {"size": 1}),
        (3, "microscopic note two", "microscopic_font", {"size": 1.5}),
        (4, "vanished clause", "vanish_attribute", {"hidden": True}),
        (5, "another concealed line", "white_font", {"color": "FFFFFF"}),
        (5, "tiny tail", "microscopic_font", {"size": 1}),
        (5, "vanish tail", "vanish_attribute", {"hidden": True}),
        (6, "final hidden remark", "white_font", {"color": "FAFAFA"}),
        (6, "second vanished bit", "vanish_attribute", {"hidden": True}),
    ]
    doc = Document()
    for p in range(7):
        para = doc.add_paragraph(f"Ordinary visible sentence number {p}. ")
        for _, text, kind, opts in [s for s in spec if s[0] == p]:
            add_run(para, text, **opts)
            manifest.append(manifest_entry(
                "tampered_hidden_text.docx", "hidden_text", kind, text, 1,
                {"paragraph": p}))
    doc.save(HERE / "tampered_hidden_text.docx")

    # benign: dark banner cover (white text on dark paragraph shading + dark cell)
    doc = Document()
    para = doc.add_paragraph()
    shade(para._p.get_or_add_pPr(), "1F3864")
    add_run(para, "ANNUAL REPORT 2026", color="FFFFFF", size=24, bold=True)
    para = doc.add_paragraph()
    shade(para._p.get_or_add_pPr(), "203864")
    add_run(para, "Confidential — prepared for the board", color="FFFFFF", size=12)
    table = doc.add_table(rows=1, cols=2)
    cell = table.cell(0, 0)
    shade(cell._tc.get_or_add_tcPr(), "1F3864")
    cell.paragraphs[0].add_run("Dark cell, white label").font.color.rgb = RGBColor.from_string("FFFFFF")
    cell = table.cell(0, 1)
    shade(cell._tc.get_or_add_tcPr(), "D9E2F3")
    cell.paragraphs[0].add_run("Light cell, dark label")
    doc.add_paragraph(ENGLISH)
    doc.save(HERE / "benign_dark_banner.docx")

    # benign: shaded table
    doc = Document()
    table = doc.add_table(rows=4, cols=2)
    for r, row in enumerate(table.rows):
        for c, cell in enumerate(row.cells):
            fill = "1F3864" if r == 0 else ("F2F2F2" if r % 2 else "FFFFFF")
            shade(cell._tc.get_or_add_tcPr(), fill)
            run = cell.paragraphs[0].add_run(f"Row {r} cell {c}")
            if r == 0:
                run.font.color.rgb = RGBColor.from_string("FFFFFF")
                run.bold = True
    doc.add_paragraph(ENGLISH)
    doc.save(HERE / "benign_shaded_table.docx")

    # benign: styled cover (large colored fonts, no shading tricks)
    doc = Document()
    add_run(doc.add_paragraph(), "Originality Checker", color="1F3864", size=28, bold=True)
    add_run(doc.add_paragraph(), "A study of submitted essays", color="404040", size=16)
    doc.add_paragraph(ENGLISH)
    doc.save(HERE / "benign_cover.docx")

    # benign: pure Cyrillic
    doc = Document()
    doc.add_paragraph(RUSSIAN)
    doc.add_paragraph(RUSSIAN)
    doc.save(HERE / "benign_cyrillic.docx")

    # benign: clean essay with references section
    doc = Document()
    doc.add_paragraph("A Study of Habit Formation")
    for _ in range(3):
        doc.add_paragraph(ENGLISH)
    doc.add_paragraph("References")
    doc.add_paragraph("Smith, J. (2020). Habits and behavior. Journal of Psychology.")
    doc.save(HERE / "benign_clean.docx")


def make_pdf_fixtures(manifest):
    pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))

    def new_canvas(name):
        return canvas.Canvas(str(HERE / name), pagesize=letter)

    # 1. homoglyphs
    c = new_canvas("tampered_homoglyphs.pdf")
    c.setFont("Arial", 11)
    for p in range(3):
        words = HOMOGLYPH_WORDS[p * 4:(p + 1) * 4]
        line = "Please verify " + " and ".join(words) + " before Friday."
        c.drawString(50, HEIGHT - 80 - p * 30, line)
        for w in words:
            manifest.append(manifest_entry(
                "tampered_homoglyphs.pdf", "replaced_character", "mixed_script_word",
                w, confusable_count(w), {"page": 1}))
    c.showPage()
    c.save()

    # 2. zero-width characters (U+FEFF/U+2060 have no Arial glyph and are dropped
    # by the PDF renderer, so the PDF fixture uses the renderable subset)
    zw_pdf = ["\u200b"] * 5 + ["\u200c"] * 2 + ["\u200d"] * 2 + \
             ["\u00ad"] * 3 + ["\u202e"] * 1
    c = new_canvas("tampered_zero_width.pdf")
    c.setFont("Arial", 11)
    base = "This ordinary sentence conceals invisible characters."
    for p in range(2):
        chars = zw_pdf[:8] if p == 0 else zw_pdf[8:]
        text = base
        for i, ch in enumerate(chars):
            pos = 5 + i * 5
            text = text[:pos] + ch + text[pos:]
        c.drawString(50, HEIGHT - 80 - p * 30, text)
        for ch in set(chars):
            manifest.append(manifest_entry(
                "tampered_zero_width.pdf", "hidden_unicode", "invisible_character",
                f"U+{ord(ch):04X}", chars.count(ch), {"page": 1}))
    c.showPage()
    c.save()

    # 3. white text
    c = new_canvas("tampered_white_text.pdf")
    white_strings = [
        ("concealed payment route", (1, 1, 1)),
        ("hidden beneficiary name", (1, 1, 1)),
        ("invisible footnote", (1, 1, 1)),
        ("near white annotation", (0.96, 0.96, 0.96)),
        ("faint watermark text", (0.97, 0.97, 0.97)),
    ]
    c.setFont("Arial", 11)
    for i, (text, color) in enumerate(white_strings):
        c.setFillColorRGB(*color)
        c.drawString(50, HEIGHT - 80 - i * 25, text)
        manifest.append(manifest_entry(
            "tampered_white_text.pdf", "hidden_text", "white_text", None,
            len(text.replace(" ", "")), {"page": 1}))
    c.setFillColorRGB(0, 0, 0)
    c.drawString(50, HEIGHT - 250, ENGLISH[:60])
    c.showPage()
    c.save()

    # 4. microscopic text
    c = new_canvas("tampered_tiny_text.pdf")
    tiny = ["microscopic disclaimer", "tiny contract term", "small print override"]
    for i, text in enumerate(tiny):
        c.setFont("Arial", 1)
        c.drawString(50, HEIGHT - 80 - i * 15, text)
        manifest.append(manifest_entry(
            "tampered_tiny_text.pdf", "hidden_text", "microscopic_font", None,
            len(text.replace(" ", "")), {"page": 1}))
    c.setFont("Arial", 11)
    c.drawString(50, HEIGHT - 200, ENGLISH[:60])
    c.showPage()
    c.save()

    # 5. out-of-bounds text (pdfplumber clips chars fully outside the page, so
    # ground-truth counts are measured from the written file's actual content)
    c = new_canvas("tampered_out_of_bounds.pdf")
    c.setFont("Arial", 11)
    oob = [("outside left margin", (-60, 100)),
           ("above page top", (50, HEIGHT + 40)),
           ("below page bottom", (50, -40))]
    for text, (x, y) in oob:
        c.drawString(x, y, text)
    c.drawString(50, HEIGHT - 80, ENGLISH[:60])
    c.showPage()
    c.save()
    import pdfplumber
    with pdfplumber.open(HERE / "tampered_out_of_bounds.pdf") as pdf:
        p = pdf.pages[0]
        n_oob = sum(1 for ch in p.chars
                    if ch["text"].strip() and (
                        ch["x0"] < -0.5 or ch["x1"] > p.width + 0.5
                        or ch["top"] < -0.5 or ch["bottom"] > p.height + 0.5))
    manifest.append(manifest_entry(
        "tampered_out_of_bounds.pdf", "hidden_text", "out_of_bounds", None,
        n_oob, {"page": 1}))

    # benign: dark banner with white text
    c = new_canvas("benign_dark_banner.pdf")
    c.setFillColorRGB(0.12, 0.22, 0.4)
    c.rect(0, HEIGHT - 120, WIDTH, 120, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Arial", 24)
    c.drawString(50, HEIGHT - 70, "ANNUAL REPORT 2026")
    c.setFont("Arial", 12)
    c.drawString(50, HEIGHT - 100, "Confidential — prepared for the board")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Arial", 11)
    import textwrap
    y = HEIGHT - 180
    for line in textwrap.wrap(ENGLISH, 90):
        c.drawString(50, y, line)
        y -= 18
    c.showPage()
    c.save()

    # benign: pure Cyrillic
    c = new_canvas("benign_cyrillic.pdf")
    c.setFont("Arial", 11)
    c.drawString(50, HEIGHT - 80, RUSSIAN[:80])
    c.drawString(50, HEIGHT - 110, RUSSIAN[80:160])
    c.drawString(50, HEIGHT - 140, RUSSIAN[160:])
    c.showPage()
    c.save()

    # benign: clean 3-page document with repeating header/footer + references
    c = new_canvas("benign_clean.pdf")
    for page in range(3):
        c.setFont("Arial", 9)
        c.drawString(50, HEIGHT - 30, "ACME UNIVERSITY — CONFIDENTIAL")
        c.drawString(50, 25, "Originality Checker Sample")
        c.setFont("Arial", 11)
        y = HEIGHT - 80
        for _ in range(4):
            c.drawString(50, y, ENGLISH[:75])
            y -= 20
        if page == 2:
            c.drawString(50, y - 20, "References")
            c.drawString(50, y - 40, "Smith, J. (2020). Habits and behavior.")
        c.showPage()
    c.save()


BENIGN = [
    "benign_dark_banner.docx", "benign_shaded_table.docx", "benign_cover.docx",
    "benign_cyrillic.docx", "benign_clean.docx",
    "benign_dark_banner.pdf", "benign_cyrillic.pdf", "benign_clean.pdf",
]


def main():
    manifest = []
    make_docx_fixtures(manifest)
    make_pdf_fixtures(manifest)
    (HERE / "manifest.json").write_text(
        json.dumps({"tampered": manifest, "benign": BENIGN}, indent=1), encoding="utf-8")
    print(f"wrote {len(manifest)} ground-truth entries, {len(BENIGN)} benign fixtures")
    for f in sorted(HERE.iterdir()):
        if f.suffix in (".docx", ".pdf"):
            print(" ", f.name)


if __name__ == "__main__":
    main()