"""Thin clients for Crossref, OpenAlex and Semantic Scholar."""
from __future__ import annotations

import os
import re
from urllib.parse import quote

import httpx

from .matching import Candidate

CONTACT = os.environ.get("CONTACT_EMAIL", "")
S2_KEY = os.environ.get("S2_API_KEY", "")


class SourceError(Exception):
    """A database could not be queried (network error, rate limit, ...)."""


def make_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    ua = "seminar-reference-checker/0.1" + (f" (mailto:{CONTACT})" if CONTACT else "")
    return httpx.AsyncClient(
        headers={"User-Agent": ua}, timeout=20.0, transport=transport, follow_redirects=True
    )


async def _get_json(client: httpx.AsyncClient, url: str, params=None, headers=None):
    try:
        resp = await client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        raise SourceError(str(exc)) from exc
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise SourceError(f"{url} returned {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise SourceError("invalid JSON") from exc


def _crossref_candidate(item: dict) -> Candidate | None:
    titles = item.get("title") or []
    if not titles:
        return None
    parts = (item.get("issued") or {}).get("date-parts") or [[None]]
    year = parts[0][0] if parts and parts[0] else None
    return Candidate(
        title=titles[0],
        year=str(year) if year else None,
        authors=[a.get("family") or a.get("name", "") for a in item.get("author", [])],
        doi=item.get("DOI"),
        url=item.get("URL"),
        source="Crossref",
    )


async def crossref_by_doi(client: httpx.AsyncClient, doi: str) -> Candidate | None:
    params = {"mailto": CONTACT} if CONTACT else None
    data = await _get_json(
        client, f"https://api.crossref.org/works/{quote(doi, safe='/')}", params
    )
    return _crossref_candidate(data["message"]) if data else None


async def crossref_search(client: httpx.AsyncClient, query: str) -> list[Candidate]:
    params = {"query.bibliographic": query, "rows": 4}
    if CONTACT:
        params["mailto"] = CONTACT
    data = await _get_json(client, "https://api.crossref.org/works", params)
    items = (data or {}).get("message", {}).get("items", [])
    return [c for c in map(_crossref_candidate, items) if c]


async def openalex_search(client: httpx.AsyncClient, title: str) -> list[Candidate]:
    params = {"search": title, "per-page": 4}
    if CONTACT:
        params["mailto"] = CONTACT
    data = await _get_json(client, "https://api.openalex.org/works", params)
    out = []
    for w in (data or {}).get("results", []):
        if not w.get("title"):
            continue
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
        authors = [
            (a.get("author", {}).get("display_name") or "").split()[-1:] or [""]
            for a in w.get("authorships", [])
        ]
        out.append(
            Candidate(
                title=w["title"],
                year=str(w["publication_year"]) if w.get("publication_year") else None,
                authors=[a[0] for a in authors],
                doi=doi,
                url=w.get("doi") or w.get("id"),
                source="OpenAlex",
            )
        )
    return out


async def semantic_scholar_search(client: httpx.AsyncClient, title: str) -> list[Candidate]:
    params = {
        "query": title,
        "limit": 4,
        "fields": "title,year,authors,externalIds,url",
    }
    headers = {"x-api-key": S2_KEY} if S2_KEY else None
    data = await _get_json(
        client, "https://api.semanticscholar.org/graph/v1/paper/search", params, headers
    )
    out = []
    for p in (data or {}).get("data", []):
        if not p.get("title"):
            continue
        out.append(
            Candidate(
                title=p["title"],
                year=str(p["year"]) if p.get("year") else None,
                authors=[(a.get("name") or "").split()[-1] for a in p.get("authors", []) if a.get("name")],
                doi=(p.get("externalIds") or {}).get("DOI"),
                url=p.get("url"),
                source="Semantic Scholar",
            )
        )
    return out


def scholar_url(text: str) -> str:
    return "https://scholar.google.com/scholar?q=" + quote(re.sub(r"\s+", " ", text)[:250])
