"""Verify one parsed reference against the databases."""
from __future__ import annotations

import asyncio

import httpx

from . import lookup
from .bibliography import Reference
from .matching import Candidate, Verdict, judge, title_score

RANK = {"found": 2, "likely": 1, "not_found": 0}


async def check_reference(client: httpx.AsyncClient, ref: Reference) -> dict:
    notes: list[str] = []
    candidates: list[Candidate] = []
    source_errors = 0
    sources_tried = 0

    async def run(coro):
        nonlocal source_errors, sources_tried
        sources_tried += 1
        try:
            return await coro
        except lookup.SourceError:
            source_errors += 1
            return None

    doi_mismatch = False
    if ref.doi:
        cand = await run(lookup.crossref_by_doi(client, ref.doi))
        if cand:
            verdict = judge(ref, cand) if ref.title else Verdict("found", 100.0)
            if verdict.status == "found" or not ref.title:
                return _result(ref, "found", verdict.score, cand, ["Verified through DOI"], False)
            doi_mismatch = True
            notes.append(f"DOI resolves to a different paper: “{cand.title}”")
        elif source_errors == 0:
            notes.append("DOI does not exist in Crossref")

    if ref.title:
        query = " ".join(filter(None, [ref.title, ref.authors[0] if ref.authors else "", ref.year or ""]))
        batches = await asyncio.gather(
            run(lookup.crossref_search(client, query)),
            run(lookup.openalex_search(client, ref.title)),
            run(lookup.semantic_scholar_search(client, ref.title)),
        )
        for batch in batches:
            candidates.extend(batch or [])

    best: tuple[Verdict, Candidate] | None = None
    for cand in candidates:
        v = judge(ref, cand)
        if best is None or (RANK[v.status], v.score) > (RANK[best[0].status], best[0].score):
            best = (v, cand)

    if best and best[0].status != "not_found":
        verdict, cand = best
        all_notes = notes + verdict.notes
        return _result(ref, verdict.status, verdict.score, cand, all_notes, False)

    if sources_tried and source_errors == sources_tried:
        return _result(ref, "error", 0.0, None, ["Could not reach any database — try again"], False)

    if not ref.title:
        notes.append("Could not extract a title from this entry — check manually")
    if ref.language == "he":
        notes.append("Hebrew-language source: international databases cover these poorly — check manually")
    elif ref.kind == "book_or_report":
        notes.append("Looks like a book or report; these are often not indexed")
    elif ref.kind == "web":
        notes.append("Web source; not expected in scholarly databases")
    if source_errors:
        notes.append(f"{source_errors} database(s) could not be queried, so this result is less certain")
    closest = best[1] if best else None
    score = best[0].score if best else 0.0
    return _result(ref, "not_found", score, closest if closest else None, notes, True)


def _result(ref: Reference, status: str, score: float, cand: Candidate | None, notes, closest_only: bool) -> dict:
    return {
        "index": ref.index,
        "status": status,
        "score": round(score, 1),
        "match": cand.to_dict() if cand else None,
        "match_is_closest_only": bool(closest_only and cand),
        "notes": notes,
        "scholar_url": lookup.scholar_url(ref.title or ref.raw),
    }
