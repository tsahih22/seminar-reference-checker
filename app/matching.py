"""Compare a parsed reference with a candidate record from a database."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .bibliography import Reference

FOUND_TITLE = 90
LIKELY_TITLE = 78


@dataclass
class Candidate:
    title: str
    year: str | None
    authors: list[str]  # surnames
    doi: str | None
    url: str | None
    source: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "year": self.year,
            "authors": self.authors,
            "doi": self.doi,
            "url": self.url,
            "source": self.source,
        }


@dataclass
class Verdict:
    status: str  # found | likely | not_found
    score: float
    notes: list[str] = field(default_factory=list)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"<[^>]+>", " ", s)  # markup in titles
    s = re.sub(r"[^\w֐-׿\s]", " ", s.casefold())
    return re.sub(r"\s+", " ", s).strip()


def title_score(cited: str, found: str) -> float:
    a, b = norm(cited), norm(found)
    if not a or not b:
        return 0.0
    score = max(fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b))
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 15 and longer.startswith(shorter):
        score = max(score, 95.0)  # subtitle missing on one side
    return float(score)


def _author_overlap(ref_authors: list[str], cand_authors: list[str]) -> bool:
    ref_n = {norm(a) for a in ref_authors if a}
    cand_n = {norm(a) for a in cand_authors if a}
    if not ref_n or not cand_n:
        return True  # nothing to compare
    for r in ref_n:
        for c in cand_n:
            if r == c or r in c or c in r:
                return True
    return False


def judge(ref: Reference, cand: Candidate) -> Verdict:
    if not ref.title:
        return Verdict("not_found", 0.0)
    score = title_score(ref.title, cand.title)
    notes: list[str] = []
    year_ok = True
    if ref.year and cand.year:
        diff = abs(int(ref.year) - int(cand.year))
        if diff > 1:
            year_ok = False
            notes.append(f"Year differs: cited {ref.year}, database says {cand.year}")
    authors_ok = _author_overlap(ref.authors, cand.authors)
    if not authors_ok:
        notes.append("Authors differ from the database record")
    if score >= FOUND_TITLE and year_ok and authors_ok:
        return Verdict("found", score)
    if score >= LIKELY_TITLE:
        if score < FOUND_TITLE:
            notes.append("Title is only a partial match")
        return Verdict("likely", score, notes)
    return Verdict("not_found", score)
