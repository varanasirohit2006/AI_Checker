"""Document parsing (AGENTS.md §6A): PDF / DOCX / TXT extraction.

Headers/footers and trailing reference sections are stripped from the scoring
text. Raw-file integrity inspection (ingest.flags.inspect_file) must run BEFORE
this module — plain-text conversion destroys color/size/position metadata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REFERENCES_HEADING = re.compile(
    r"^\s*(references|bibliography|works cited|citations)\s*:?\s*$",
    re.IGNORECASE,
)


@dataclass
class Paragraph:
    text: str
    index: int
    page: int | None = None


@dataclass
class ParsedDocument:
    source: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    n_pages: int | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.paragraphs)


def _strip_references(paragraphs: list[Paragraph]) -> list[Paragraph]:
    for i, p in enumerate(paragraphs):
        if REFERENCES_HEADING.match(p.text):
            return paragraphs[:i]
    return paragraphs


def _parse_docx(path: Path) -> ParsedDocument:
    from docx import Document

    from ingest.flags import _iter_docx_paragraphs

    document = Document(str(path))
    paragraphs = []
    # python-docx body iteration excludes section headers/footers by design.
    for idx, (para, _cell) in enumerate(_iter_docx_paragraphs(document)):
        text = para.text.strip()
        if text:
            paragraphs.append(Paragraph(text=text, index=idx))
    return ParsedDocument(source=path.name,
                          paragraphs=_strip_references(paragraphs))


def _parse_pdf(path: Path) -> ParsedDocument:
    import pdfplumber

    with pdfplumber.open(str(path)) as pdf:
        n_pages = len(pdf.pages)
        page_lines: list[list[str]] = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            page_lines.append([ln.strip() for ln in text.splitlines() if ln.strip()])

        # Header/footer heuristic: a first/last line repeated on >=60% of pages
        # (min 2) is furniture, not content.
        edge_counts: dict[str, int] = {}
        for lines in page_lines:
            if not lines:
                continue
            for edge in {lines[0], lines[-1]}:
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
        threshold = max(2, int(0.6 * n_pages))
        furniture = {ln for ln, n in edge_counts.items()
                     if n >= threshold and n_pages >= 2}

        paragraphs = []
        idx = 0
        in_references = False
        for page_no, lines in enumerate(page_lines, start=1):
            buf: list[str] = []
            for ln in lines:
                if REFERENCES_HEADING.match(ln):
                    in_references = True
                if in_references or ln in furniture:
                    continue
                buf.append(ln)
            text = " ".join(buf).strip()
            if text:
                paragraphs.append(Paragraph(text=text, index=idx, page=page_no))
                idx += 1
    return ParsedDocument(source=path.name,
                          paragraphs=_strip_references(paragraphs),
                          n_pages=n_pages)


def _parse_txt(path: Path) -> ParsedDocument:
    text = path.read_text(encoding="utf-8-sig")
    paragraphs = []
    for idx, block in enumerate(re.split(r"\n\s*\n", text)):
        block = block.strip()
        if block:
            paragraphs.append(Paragraph(text=block, index=idx))
    return ParsedDocument(source=path.name,
                          paragraphs=_strip_references(paragraphs))


def parse(path: str | Path) -> ParsedDocument:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix in (".txt", ".md"):
        return _parse_txt(path)
    raise ValueError(f"Unsupported file type: {suffix}")


parse_file = parse
