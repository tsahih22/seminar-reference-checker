import json

import httpx
from fastapi.testclient import TestClient

from app import main
from tests.conftest import make_docx, make_pdf
from tests.test_matching import CROSSREF_ITEM, handler_factory


def client_with(handler):
    main.client_factory = lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TestClient(main.app)


def events(resp):
    return [json.loads(l) for l in resp.text.splitlines() if l.strip()]


def test_docx_end_to_end(paper_text):
    c = client_with(handler_factory(crossref_items=[CROSSREF_ITEM]))
    resp = c.post("/api/check", files={"file": ("paper.docx", make_docx(paper_text))})
    assert resp.status_code == 200
    ev = events(resp)
    assert ev[0]["type"] == "parsed" and len(ev[0]["references"]) == 6
    assert ev[0]["intext"]["cited_not_in_bibliography"][0]["citation"] == "Smith, 2021"
    results = {e["index"]: e for e in ev if e["type"] == "result"}
    assert len(results) == 6 and results[3]["status"] == "found"
    assert ev[-1]["type"] == "done"


def test_pdf_extraction(paper_text):
    ascii_only = "\n".join(  # the test PDF font has no Hebrew glyphs
        l for l in paper_text.splitlines() if not any("\u0590" <= ch <= "\u05ff" for ch in l)
    )
    c = client_with(handler_factory())
    resp = c.post("/api/check", files={"file": ("paper.pdf", make_pdf(ascii_only))})
    ev = events(resp)
    assert ev[0]["bibliography_found"] and len(ev[0]["references"]) == 5


def test_rejects_other_types():
    c = client_with(handler_factory())
    resp = c.post("/api/check", files={"file": ("x.txt", b"hello")})
    assert resp.status_code == 400


def test_corrupt_file():
    c = client_with(handler_factory())
    resp = c.post("/api/check", files={"file": ("x.pdf", b"not a pdf")})
    assert resp.status_code == 422


def test_index_served():
    assert "Seminar Reference Checker" in TestClient(main.app).get("/").text
