from app.bibliography import extract_references
from app.intext import cross_check, find_citations


def test_finds_parenthetical_and_narrative(paper_text):
    body, _, _ = extract_references(paper_text)
    found = {(c.surname, c.year) for c in find_citations(body)}
    assert ("Cohen", "1988") in found
    assert ("Bandura", "1963") in found
    assert ("Kahneman", "1979") in found
    assert ("Smith", "2021") in found
    assert ("Levi", "2019") in found
    assert ("Association", "2020") in found


def test_cross_check(paper_text):
    body, refs, _ = extract_references(paper_text)
    result = cross_check(body, refs)
    missing = [m["citation"] for m in result["cited_not_in_bibliography"]]
    assert missing == ["Smith, 2021"]
    assert result["bibliography_not_cited"] == [5]  # the Hebrew entry is never cited


def test_hebrew_citation_with_prefix():
    text = "לפי כהן ולוי (2020) וגם (לכהן, 2020).\nרשימת מקורות\nכהן, ד., & לוי, מ. (2020). השפעת הלמידה מרחוק על הישגים אקדמיים. מגמות, 55(2), 100–125."
    body, refs, _ = extract_references(text)
    result = cross_check(body, refs)
    assert result["bibliography_not_cited"] == []
