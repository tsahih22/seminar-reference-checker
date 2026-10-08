"""Locate the bibliography in a paper and parse APA-style entries.

Rule-based on purpose (no LLM). Handles English and Hebrew entries.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

HEADING_WORDS = (
    r"references?|reference list|bibliography|works cited|"
    r"מקורות|רשימת מקורות|ביבליוגרפיה|רשימה ביבליוגרפית|רשימת מראי מקום|מראי מקום|מקורות ביבליוגרפיים"
)
HEADING_RE = re.compile(
    rf"^\s*(?:\d+[.)]?\s*)?(?:{HEADING_WORDS})\s*:?\s*$", re.IGNORECASE
)
END_HEADING_RE = re.compile(
    r"^\s*(?:appendix|appendices|נספח|נספחים)\b", re.IGNORECASE
)

HE = r"֐-׿"
LATIN_START = re.compile(r"^[A-Z][A-Za-z'’\-]+(?: [A-Za-z'’\-]+)?,\s+[A-Z]\.")
HEBREW_START = re.compile(rf"^[{HE}'\"׳״\-]+(?: [{HE}'\"׳״\-]+)?,\s+[{HE}]['׳]?\.")
YEAR_PAREN_START = re.compile(r"^[^()]{2,150}\(\s*(?:\d{4}[a-z]?|n\.d\.)\s*[),]")
NUMBER_PREFIX = re.compile(r"^\s*(?:\[\d+\]|\d{1,3}[.)])\s+")
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\(\s*((?:19|20)\d{2})[a-z]?\s*[),]")
ND_RE = re.compile(r"\(\s*n\.d\.\s*\)", re.IGNORECASE)
HEBREW_CHAR = re.compile(rf"[{HE}]")
LATIN_SURNAME = re.compile(
    r"([^\s,&.()]+(?:[ '’\-][A-Za-z][^\s,&.()]*)*),\s*(?:[A-Z]\.[\s\-]*)+"
)
HEBREW_SURNAME = re.compile(
    rf"([{HE}'\"׳״\-]+(?: [{HE}'\"׳״\-]+)?),\s*(?:[{HE}]['׳]?\.\s*)+"
)
TITLE_END = re.compile(r"(?<![A-Z])(?<![A-Z]\.[A-Z])[.?!](?=\s|$)")
VOLUME_PAGES = re.compile(r"\b\d+\s*\(\d+\)|\b\d+\s*[,:]\s*\d+\s*[–\-]\s*\d+|\b\d+\s*[–\-]\s*\d+\b")


@dataclass
class Reference:
    index: int
    raw: str
    authors: list[str] = field(default_factory=list)  # surnames (or organisation name)
    year: str | None = None
    title: str | None = None
    container: str | None = None
    doi: str | None = None
    kind: str = "article"  # article | book_or_report | web
    language: str = "en"  # en | he

    def to_dict(self) -> dict:
        return asdict(self)


def split_body_and_references(text: str) -> tuple[str, str | None]:
    """Return (body, reference_section). Uses the last matching heading."""
    lines = text.splitlines()
    heading_at = None
    for i, line in enumerate(lines):
        if HEADING_RE.match(line):
            heading_at = i
    if heading_at is None:
        return text, None
    ref_lines = lines[heading_at + 1 :]
    for j, line in enumerate(ref_lines):
        if END_HEADING_RE.match(line):
            ref_lines = ref_lines[:j]
            break
    return "\n".join(lines[:heading_at]), "\n".join(ref_lines)


def _is_entry_start(line: str) -> bool:
    line = NUMBER_PREFIX.sub("", line)
    return bool(
        LATIN_START.match(line) or HEBREW_START.match(line) or YEAR_PAREN_START.match(line)
    )


def _entry_ended(buf: str) -> bool:
    buf = buf.rstrip()
    return bool(buf) and (buf[-1] in ".)?!" or buf[-1].isdigit() or "doi.org" in buf[-40:])


def split_entries(ref_text: str) -> list[str]:
    entries: list[str] = []
    for block in re.split(r"\n\s*\n", ref_text):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        lines = [l for l in lines if not re.fullmatch(r"\d{1,4}", l)]  # page numbers
        if not lines:
            continue
        current = ""
        for line in lines:
            if current and _is_entry_start(line) and _entry_ended(current):
                entries.append(current)
                current = line
            else:
                current = f"{current} {line}".strip() if current else line
        if current:
            entries.append(current)
    cleaned = [re.sub(r"\s+", " ", NUMBER_PREFIX.sub("", e)).strip() for e in entries]
    return [e for e in cleaned if len(e) > 15]


def parse_entry(index: int, raw: str) -> Reference:
    ref = Reference(index=index, raw=raw)
    letters = [c for c in raw if c.isalpha()]
    he_share = sum(1 for c in letters if HEBREW_CHAR.match(c)) / max(len(letters), 1)
    ref.language = "he" if he_share > 0.3 else "en"

    m = DOI_RE.search(raw)
    if m:
        ref.doi = m.group(0).rstrip(".,;)")

    year_m = YEAR_RE.search(raw)
    author_part = raw
    rest = raw
    if year_m:
        ref.year = year_m.group(1)
        author_part = raw[: year_m.start()]
        rest = raw[year_m.end() :]
    elif ND_RE.search(raw):
        nd = ND_RE.search(raw)
        author_part, rest = raw[: nd.start()], raw[nd.end() :]
    else:
        fallback = re.search(r"\b((?:19|20)\d{2})\b", raw)
        if fallback:
            ref.year = fallback.group(1)
            author_part = raw[: fallback.start()]
            rest = raw[fallback.end() :]

    surnames = LATIN_SURNAME.findall(author_part) + HEBREW_SURNAME.findall(author_part)
    if surnames:
        # keep citation order
        positions = []
        for s in surnames:
            positions.append((author_part.find(s), s))
        ref.authors = [s for _, s in sorted(positions)]
    else:
        org = author_part.strip().rstrip(".,; ")
        if org:
            ref.authors = [org]

    rest = rest.lstrip(" ).,:").strip()
    title_m = TITLE_END.search(rest)
    if title_m:
        ref.title = rest[: title_m.end()].strip().rstrip(".").strip()
        remainder = rest[title_m.end() :].strip()
    else:
        ref.title = rest.strip().rstrip(".").strip() or None
        remainder = ""
    if ref.title:
        ref.title = re.sub(r"\s*\[[^\]]*\]\s*$", "", ref.title).strip()

    if remainder:
        ref.container = re.split(r",\s*\d|\s*\(\d", remainder, maxsplit=1)[0].strip(" .,") or None

    if ref.doi or VOLUME_PAGES.search(remainder):
        ref.kind = "article"
    elif re.search(r"https?://|retrieved from|available at", raw, re.IGNORECASE):
        ref.kind = "web"
    else:
        ref.kind = "book_or_report"
    return ref


def extract_references(text: str) -> tuple[str, list[Reference], bool]:
    """Return (body_text, references, section_found)."""
    body, ref_text = split_body_and_references(text)
    if ref_text is None:
        return text, [], False
    refs = [parse_entry(i, e) for i, e in enumerate(split_entries(ref_text), start=1)]
    return body, refs, True
