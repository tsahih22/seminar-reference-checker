"""Turn an uploaded PDF or DOCX into plain text.

DOCX paragraphs are separated by blank lines so each bibliography entry
stays intact. PDF text keeps one line per visual line.
"""
from __future__ import annotations

import io
import re

FINAL_FORMS = "ךםןףץ"
HEBREW_RE = re.compile(r"[֐-׿]")
ASCII_RUN_RE = re.compile(r"[\x00-\x7F]+")


class UnsupportedFile(ValueError):
    pass


def extract_text(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return _pdf_text(data)
    if name.endswith(".docx"):
        return _docx_text(data)
    raise UnsupportedFile("Only .pdf and .docx files are supported.")


def _docx_text(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())


def _pdf_text(data: bytes) -> str:
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines.extend(fix_visual_hebrew(line) for line in text.splitlines())
    return "\n".join(lines)


def looks_reversed(line: str) -> bool:
    """Hebrew in some PDFs comes out in visual (reversed) order.

    In correct text, final-form letters (ך ם ן ף ץ) end words; in reversed text
    they start them.
    """
    if not HEBREW_RE.search(line):
        return False
    starts = ends = 0
    for token in line.split():
        letters = [c for c in token if HEBREW_RE.match(c)]
        if len(letters) < 2:
            continue
        if letters[0] in FINAL_FORMS:
            starts += 1
        if letters[-1] in FINAL_FORMS:
            ends += 1
    return starts > ends


def fix_visual_hebrew(line: str) -> str:
    if not looks_reversed(line):
        return line
    flipped = line[::-1]
    # Latin words, numbers and punctuation runs were reversed too; restore them.
    return ASCII_RUN_RE.sub(lambda m: m.group(0)[::-1], flipped)
