from app.bibliography import extract_references, parse_entry, split_body_and_references


def test_finds_heading_and_splits(paper_text):
    body, refs, found = extract_references(paper_text)
    assert found
    assert "Introduction" in body and "Publication manual" not in body
    assert len(refs) == 6  # multi-line Levi entry stays one entry


def test_parses_article_with_doi(paper_text):
    _, refs, _ = extract_references(paper_text)
    k = refs[2]
    assert k.authors == ["Kahneman", "Tversky"]
    assert k.year == "1979"
    assert k.title == "Prospect theory: An analysis of decision under risk"
    assert k.doi == "10.2307/1914185"
    assert k.kind == "article"
    assert k.container == "Econometrica"


def test_multiline_entry_joined(paper_text):
    _, refs, _ = extract_references(paper_text)
    assert refs[3].title == "Fake study of imaginary effects on invisible students"


def test_book_detected(paper_text):
    _, refs, _ = extract_references(paper_text)
    assert refs[0].kind == "book_or_report"
    assert refs[0].authors == ["Cohen"]


def test_hebrew_entry(paper_text):
    _, refs, _ = extract_references(paper_text)
    h = refs[4]
    assert h.language == "he"
    assert h.authors == ["כהן", "לוי"]
    assert h.year == "2020"
    assert h.title.startswith("השפעת הלמידה")


def test_organisation_author(paper_text):
    _, refs, _ = extract_references(paper_text)
    assert refs[5].authors == ["American Psychological Association"]


def test_no_heading():
    body, refs, found = extract_references("Just some text without any references.")
    assert not found and refs == []


def test_hebrew_heading_and_appendix_stop():
    text = "גוף\nרשימת מקורות\nCohen, J. (1988). Statistical power analysis. Erlbaum.\nנספח א\nlots of appendix"
    body, ref_text = split_body_and_references(text)
    assert ref_text.strip().startswith("Cohen") and "appendix" not in ref_text


def test_numbered_entries():
    text = "References\n1. Smith, A. (2020). A title here that is long. Journal of Things, 3(1), 1-9.\n2. Jones, B. (2018). Another title that is long. Journal of Stuff, 4(2), 10-20."
    _, refs, _ = extract_references(text)
    assert [r.authors for r in refs] == [["Smith"], ["Jones"]]
