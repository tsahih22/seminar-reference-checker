"""Cross-check in-text citations such as (Cohen, 2019) against the bibliography."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .bibliography import Reference

HE = r"֐-׿"
WORD = rf"[A-Za-z{HE}][\w{HE}'’׳\-]*"
YEAR = r"(?:19|20)\d{2}"
PAREN_RE = re.compile(rf"\(([^()]*?{YEAR}[a-z]?[^()]*?)\)")
YEAR_IN_PART = re.compile(rf"({YEAR})[a-z]?")
NARRATIVE_RE = re.compile(
    rf"({WORD}(?:\s+(?:&|and|ו)\s*{WORD}|\s+et al\.?)?)\s*\(\s*({YEAR})[a-z]?\s*\)"
)
STOPWORDS = {"see", "e.g.", "cf.", "also", "and", "et", "al", "al.", "in", "p", "pp"}


@dataclass
class Citation:
    text: str
    surname: str
    year: str


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w֐-׿]", "", s.casefold())


def _first_author_token(author_text: str) -> str | None:
    text = re.sub(r"\bet al\.?", " ", author_text)
    text = re.sub(r"\b(?:see|e\.g\.|cf\.|also|in)\b", " ", text, flags=re.IGNORECASE)
    tokens = re.findall(WORD, text)
    tokens = [t for t in tokens if t.casefold() not in STOPWORDS]
    if not tokens:
        return None
    if len(tokens) > 1 and ("&" in author_text or re.search(r"\band\b", author_text)):
        return tokens[0]
    if len(tokens) > 1 and re.search(rf"[{HE}]", tokens[-1]) and tokens[-1].startswith("ו"):
        return tokens[0]
    if "et al" in author_text:
        return tokens[0]
    return tokens[-1]


def find_citations(body: str) -> list[Citation]:
    found: list[Citation] = []
    for m in PAREN_RE.finditer(body):
        for part in m.group(1).split(";"):
            ym = YEAR_IN_PART.search(part)
            if not ym:
                continue
            token = _first_author_token(part[: ym.start()])
            if token:
                found.append(Citation(part.strip(), token, ym.group(1)))
    for m in NARRATIVE_RE.finditer(body):
        token = _first_author_token(m.group(1))
        if token:
            found.append(Citation(m.group(0), token, m.group(2)))
    return found


def _ref_tokens(ref: Reference) -> set[str]:
    toks: set[str] = set()
    for a in ref.authors:
        for w in re.findall(WORD, a):
            toks.add(_norm(w))
    return toks


def _cite_matches(cite: Citation, ref: Reference) -> bool:
    if cite.year != ref.year:
        return False
    tokens = _ref_tokens(ref)
    name = _norm(cite.surname)
    if name in tokens:
        return True
    # Hebrew prefixes attached to the name: ל/ב/מ/ה/ו/ש/כ
    return bool(HEBREW_PREFIX.match(cite.surname)) and name[1:] in tokens


HEBREW_PREFIX = re.compile(rf"^[לבמהושכ][{HE}]{{2,}}")


def cross_check(body: str, refs: list[Reference]) -> dict:
    citations = find_citations(body)
    unique: dict[tuple[str, str], Citation] = {}
    for c in citations:
        unique.setdefault((_norm(c.surname), c.year), c)

    uncited = [
        r.index
        for r in refs
        if not any(_cite_matches(c, r) for c in unique.values())
    ]
    missing = [
        {"citation": f"{c.surname}, {c.year}", "example": c.text}
        for c in unique.values()
        if not any(_cite_matches(c, r) for r in refs)
    ]
    return {
        "citations_found": len(citations),
        "cited_not_in_bibliography": missing,
        "bibliography_not_cited": uncited,
    }
