"""Red Flag / integrity inspection (AGENTS.md §6A).

Three flag categories:
  * replaced_character — mixed-script words (Latin + Cyrillic/Greek/Armenian
    lookalikes), verified with the confusable-homoglyphs library.
  * hidden_unicode — zero-width / invisible / bidi-override characters.
  * hidden_text — near-white font, microscopic font (<2pt), Word `vanish`
    attribute, or PDF characters outside the visible page.

Order of operations: inspect the RAW file (inspect_docx / inspect_pdf) before
plain-text extraction; scan_text covers character-level flags on extracted text.

False-positive guardrails:
  * white text over a dark banner / shaded table cell is NOT flagged;
  * pure non-Latin paragraphs are NOT flagged (only mixed-script words);
  * repeated alerts are grouped per paragraph (DOCX) or page (PDF).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from confusable_homoglyphs import confusables

REPLACED_CHARACTER = "replaced_character"
HIDDEN_UNICODE = "hidden_unicode"
HIDDEN_TEXT = "hidden_text"

# Invisible / zero-width / bidi-control characters (codepoint -> name).
HIDDEN_CODEPOINTS = {
    0x00AD: "SOFT HYPHEN",
    0x034F: "COMBINING GRAPHEME JOINER",
    0x061C: "ARABIC LETTER MARK",
    0x180E: "MONGOLIAN VOWEL SEPARATOR",
    0x200B: "ZERO WIDTH SPACE",
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
    0x200E: "LEFT-TO-RIGHT MARK",
    0x200F: "RIGHT-TO-LEFT MARK",
    0x202A: "LEFT-TO-RIGHT EMBEDDING",
    0x202B: "RIGHT-TO-LEFT EMBEDDING",
    0x202C: "POP DIRECTIONAL FORMATTING",
    0x202D: "LEFT-TO-RIGHT OVERRIDE",
    0x202E: "RIGHT-TO-LEFT OVERRIDE",
    0x2060: "WORD JOINER",
    0x2061: "FUNCTION APPLICATION",
    0x2062: "INVISIBLE TIMES",
    0x2063: "INVISIBLE SEPARATOR",
    0x2064: "INVISIBLE PLUS",
    0x2066: "LEFT-TO-RIGHT ISOLATE",
    0x2067: "RIGHT-TO-LEFT ISOLATE",
    0x2068: "FIRST STRONG ISOLATE",
    0x2069: "POP DIRECTIONAL ISOLATE",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE / BOM",
    0xFFF9: "INTERLINEAR ANNOTATION ANCHOR",
    0xFFFA: "INTERLINEAR ANNOTATION SEPARATOR",
    0xFFFB: "INTERLINEAR ANNOTATION TERMINATOR",
}
# Unicode tag block (ASCII smuggling).
HIDDEN_CODEPOINTS.update({cp: "TAG CHARACTER" for cp in range(0xE0000, 0xE0080)})

WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

NEAR_WHITE_MIN = 240      # per 8-bit channel
NEAR_WHITE_MIN_F = 0.94   # per float channel
DARK_LUMINANCE_MAX = 0.45
MICROSCOPIC_PT = 2.0


@dataclass
class Flag:
    category: str
    kind: str
    location: dict
    count: int = 0
    instances: list = field(default_factory=list)

    def summary(self) -> str:
        loc = ", ".join(f"{k}={v}" for k, v in self.location.items())
        return f"[{self.category}/{self.kind}] {loc} x{self.count}"


def _latin_homoglyph(ch: str) -> str | None:
    entries = confusables.confusables_data.get(ch)
    if entries:
        candidate = entries[0]["c"]
        if confusables.alias(candidate) == "LATIN":
            return candidate
    return None


def _has_latin(word: str) -> bool:
    return any(confusables.alias(c) == "LATIN" for c in word)


def mixed_script_instances(text: str, base_offset: int = 0) -> list[dict]:
    """One instance per confusable non-Latin character inside a mixed-script word."""
    out = []
    for m in WORD_RE.finditer(text):
        word = m.group()
        if not confusables.is_mixed_script(word) or not _has_latin(word):
            continue
        for info in confusables.is_confusable(word, preferred_aliases=["latin"]):
            ch = info["character"]
            if confusables.alias(ch) == "LATIN":
                continue
            out.append({
                "word": word,
                "char": ch,
                "codepoint": f"U+{ord(ch):04X}",
                "script": info["alias"],
                "latin": _latin_homoglyph(ch),
                "offset": base_offset + m.start() + word.index(ch),
            })
    return out


def hidden_unicode_instances(text: str, base_offset: int = 0) -> list[dict]:
    out = []
    for i, ch in enumerate(text):
        cp = ord(ch)
        if cp in HIDDEN_CODEPOINTS:
            out.append({
                "char": ch,
                "codepoint": f"U+{cp:04X}",
                "name": HIDDEN_CODEPOINTS[cp],
                "offset": base_offset + i,
            })
    return out


def _group(category: str, kind: str, location: dict, instances: list[dict]) -> Flag:
    return Flag(category=category, kind=kind, location=location,
                count=len(instances), instances=instances)


def scan_text(text: str, *, source: str | None = None, page: int | None = None,
              paragraph: int | None = None, base_offset: int = 0) -> list[Flag]:
    """Character-level flags (mixed-script words + hidden unicode) for one text unit."""
    loc = {}
    if source is not None:
        loc["source"] = source
    if page is not None:
        loc["page"] = page
    if paragraph is not None:
        loc["paragraph"] = paragraph
    flags = []
    replaced = mixed_script_instances(text, base_offset)
    if replaced:
        flags.append(_group(REPLACED_CHARACTER, "mixed_script_word", loc, replaced))
    hidden = hidden_unicode_instances(text, base_offset)
    if hidden:
        flags.append(_group(HIDDEN_UNICODE, "invisible_character", loc, hidden))
    return flags


# --------------------------------------------------------------------------
# DOCX raw inspection
# --------------------------------------------------------------------------

def _luminance_rgb(r: float, g: float, b: float) -> float:
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _fill_is_dark(fill: str | None) -> bool:
    if not fill or fill.lower() == "auto":
        return False
    try:
        r, g, b = (int(fill[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return False
    return _luminance_rgb(r, g, b) <= DARK_LUMINANCE_MAX


def _shd_fill(elm) -> str | None:
    if elm is None:
        return None
    from docx.oxml.ns import qn
    shd = elm.find(qn("w:shd"))
    if shd is None:
        return None
    return shd.get(qn("w:fill"))


def _paragraph_shading(paragraph) -> str | None:
    return _shd_fill(paragraph._p.pPr)


def _cell_shading(cell) -> str | None:
    return _shd_fill(cell._tc.tcPr)


def _iter_docx_paragraphs(document):
    """Yield (paragraph, cell_or_None) in body order, including table cells."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    def walk(parent_elm, cell=None):
        for child in parent_elm.iterchildren():
            if child.tag.endswith("}p"):
                yield Paragraph(child, document), cell
            elif child.tag.endswith("}tbl"):
                table = Table(child, document)
                for row in table.rows:
                    for c in row.cells:
                        yield from walk(c._tc, c)

    yield from walk(document.element.body)


def inspect_docx(path: str | Path) -> list[Flag]:
    from docx import Document

    path = Path(path)
    document = Document(str(path))
    flags: list[Flag] = []
    hidden_by_para: dict[tuple[int, str], list[dict]] = {}

    for idx, (paragraph, cell) in enumerate(_iter_docx_paragraphs(document)):
        fills = [_paragraph_shading(paragraph)]
        if cell is not None:
            fills.append(_cell_shading(cell))
        on_dark = any(_fill_is_dark(f) for f in fills)

        offset = 0
        flags.extend(scan_text(paragraph.text, source=path.name, paragraph=idx))
        for run in paragraph.runs:
            text = run.text
            if not text.strip():
                offset += len(text)
                continue
            kinds = []
            rgb = run.font.color.rgb if run.font.color and run.font.color.type is not None else None
            if rgb is not None and min(rgb[0], rgb[1], rgb[2]) >= NEAR_WHITE_MIN and not on_dark:
                kinds.append(("white_font", {"color": str(rgb)}))
            size = run.font.size
            if size is not None and size.pt < MICROSCOPIC_PT:
                kinds.append(("microscopic_font", {"size_pt": size.pt}))
            if run.font.hidden:
                kinds.append(("vanish_attribute", {}))
            for kind, extra in kinds:
                hidden_by_para.setdefault((idx, kind), []).append(
                    {"text": text, "paragraph": idx, "offset": offset, **extra})
            offset += len(text)

    for (idx, kind), instances in hidden_by_para.items():
        flags.append(_group(HIDDEN_TEXT, kind,
                            {"source": path.name, "paragraph": idx}, instances))
    return flags


# --------------------------------------------------------------------------
# PDF raw inspection
# --------------------------------------------------------------------------

def _color_components(color) -> tuple[float, ...] | None:
    if color is None:
        return None
    if isinstance(color, (list, tuple)):
        return tuple(float(c) for c in color)
    return (float(color),)


def _is_near_white(color) -> bool:
    comp = _color_components(color)
    if comp is None:
        return False
    if len(comp) == 1:
        return comp[0] >= NEAR_WHITE_MIN_F
    if len(comp) == 3:
        return all(c >= NEAR_WHITE_MIN_F for c in comp)
    if len(comp) == 4:  # CMYK -> approximate RGB
        c, m, y, k = comp
        r, g, b = ((1 - min(1, x + k)) for x in (c, m, y))
        return all(v >= NEAR_WHITE_MIN_F for v in (r, g, b))
    return False


def _is_dark_color(color) -> bool:
    comp = _color_components(color)
    if comp is None:
        return False
    if len(comp) == 1:
        return comp[0] <= DARK_LUMINANCE_MAX
    if len(comp) == 3:
        return _luminance_rgb(*(c * 255 for c in comp)) <= DARK_LUMINANCE_MAX
    if len(comp) == 4:
        c, m, y, k = comp
        r, g, b = ((1 - min(1, x + k)) for x in (c, m, y))
        return _luminance_rgb(r * 255, g * 255, b * 255) <= DARK_LUMINANCE_MAX
    return False


def _dark_regions(page) -> list[tuple[float, float, float, float]]:
    regions = []
    for obj in list(page.rects) + list(page.curves):
        if obj.get("fill") and _is_dark_color(obj.get("non_stroking_color")):
            regions.append((obj["x0"], obj["top"], obj["x1"], obj["bottom"]))
    return regions


def _covered(x: float, y: float, regions) -> bool:
    return any(x0 - 1 <= x <= x1 + 1 and top - 1 <= y <= bottom + 1
               for x0, top, x1, bottom in regions)


def inspect_pdf(path: str | Path) -> list[Flag]:
    import pdfplumber

    path = Path(path)
    flags: list[Flag] = []
    with pdfplumber.open(str(path)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            flags.extend(scan_text(page.extract_text() or "",
                                   source=path.name, page=page_no))
            dark = _dark_regions(page)
            width, height = page.width, page.height
            hidden_by_kind: dict[str, list[dict]] = {}
            for ch in page.chars:
                text = ch.get("text", "")
                if not text or not text.strip():
                    continue
                cx = (ch["x0"] + ch["x1"]) / 2
                cy = (ch["top"] + ch["bottom"]) / 2
                bbox = [round(ch[k], 2) for k in ("x0", "top", "x1", "bottom")]
                kinds = []
                if _is_near_white(ch.get("non_stroking_color")) and not _covered(cx, cy, dark):
                    kinds.append(("white_text", {"color": ch.get("non_stroking_color")}))
                if ch.get("size", 12) < MICROSCOPIC_PT:
                    kinds.append(("microscopic_font", {"size_pt": round(ch["size"], 2)}))
                if (ch["x0"] < -0.5 or ch["x1"] > width + 0.5
                        or ch["top"] < -0.5 or ch["bottom"] > height + 0.5):
                    kinds.append(("out_of_bounds", {"page_size": [width, height]}))
                for kind, extra in kinds:
                    hidden_by_kind.setdefault(kind, []).append(
                        {"text": text, "page": page_no, "bbox": bbox, **extra})
            for kind, instances in hidden_by_kind.items():
                flags.append(_group(HIDDEN_TEXT, kind,
                                    {"source": path.name, "page": page_no}, instances))
    return flags


def inspect_file(path: str | Path) -> list[Flag]:
    """Raw-file inspection dispatch (call BEFORE plain-text extraction)."""
    suffix = Path(path).suffix.lower()
    if suffix == ".docx":
        return inspect_docx(path)
    if suffix == ".pdf":
        return inspect_pdf(path)
    if suffix in (".txt", ".md"):
        text = Path(path).read_text(encoding="utf-8")
        flags = []
        for i, para in enumerate(re.split(r"\n\s*\n", text)):
            flags.extend(scan_text(para, source=Path(path).name, paragraph=i))
        return flags
    raise ValueError(f"Unsupported file type: {suffix}")