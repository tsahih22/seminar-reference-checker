import asyncio

import httpx

from app.bibliography import Reference
from app.checker import check_reference
from app.matching import Candidate, judge


def ref(**kw):
    base = dict(index=1, raw="raw", authors=["Kahneman", "Tversky"], year="1979",
                title="Prospect theory: An analysis of decision under risk", kind="article")
    base.update(kw)
    return Reference(**base)


def cand(**kw):
    base = dict(title="Prospect Theory: An Analysis of Decision under Risk", year="1979",
                authors=["Kahneman", "Tversky"], doi="10.2307/1914185", url="https://x", source="Crossref")
    base.update(kw)
    return Candidate(**base)


def test_found():
    assert judge(ref(), cand()).status == "found"


def test_wrong_year_is_likely():
    v = judge(ref(), cand(year="2005"))
    assert v.status == "likely" and any("Year differs" in n for n in v.notes)


def test_wrong_authors_is_likely():
    v = judge(ref(), cand(authors=["Nobody"]))
    assert v.status == "likely"


def test_unrelated_title():
    assert judge(ref(), cand(title="Deep learning for protein folding")).status == "not_found"


def handler_factory(crossref_items=(), openalex=(), s2=(), doi_item=None, fail=False):
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(503)
        url = str(request.url)
        if "api.crossref.org/works/" in url:
            if doi_item is None:
                return httpx.Response(404)
            return httpx.Response(200, json={"message": doi_item})
        if "api.crossref.org/works" in url:
            return httpx.Response(200, json={"message": {"items": list(crossref_items)}})
        if "openalex" in url:
            return httpx.Response(200, json={"results": list(openalex)})
        if "semanticscholar" in url:
            return httpx.Response(200, json={"data": list(s2)})
        return httpx.Response(404)
    return handler


def run(handler, r):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await check_reference(c, r)
    return asyncio.run(go())


CROSSREF_ITEM = {
    "title": ["Prospect theory: An analysis of decision under risk"],
    "issued": {"date-parts": [[1979]]},
    "author": [{"family": "Kahneman"}, {"family": "Tversky"}],
    "DOI": "10.2307/1914185", "URL": "https://doi.org/10.2307/1914185",
}


def test_found_via_search():
    res = run(handler_factory(crossref_items=[CROSSREF_ITEM]), ref())
    assert res["status"] == "found" and res["match"]["source"] == "Crossref"


def test_doi_verified():
    res = run(handler_factory(doi_item=CROSSREF_ITEM), ref(doi="10.2307/1914185"))
    assert res["status"] == "found" and "DOI" in res["notes"][0]


def test_doi_points_elsewhere_and_nothing_else_found():
    other = {**CROSSREF_ITEM, "title": ["Completely different paper about whales"]}
    res = run(handler_factory(doi_item=other), ref(doi="10.1/zzz"))
    assert res["status"] == "not_found"
    assert any("different paper" in n for n in res["notes"])


def test_not_found_hebrew_note():
    r = ref(language="he", title="השפעת הלמידה מרחוק", authors=["כהן"], year="2020")
    res = run(handler_factory(), r)
    assert res["status"] == "not_found" and any("Hebrew" in n for n in res["notes"])


def test_all_sources_down_is_error_not_not_found():
    res = run(handler_factory(fail=True), ref())
    assert res["status"] == "error"
