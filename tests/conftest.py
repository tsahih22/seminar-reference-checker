import io

import pytest


@pytest.fixture
def apa_references():
    return """Cohen, J. (1988). Statistical power analysis for the behavioral sciences (2nd ed.). Lawrence Erlbaum Associates.
Bandura, A., & Walters, R. H. (1963). Social learning and personality development. Holt, Rinehart & Winston.
Kahneman, D., & Tversky, A. (1979). Prospect theory: An analysis of decision under risk. Econometrica, 47(2), 263–291. https://doi.org/10.2307/1914185
Levi, R. (2019). Fake study of imaginary effects on invisible
students. Journal of Nonexistent Results, 12(3), 45–67.
כהן, ד., & לוי, מ. (2020). השפעת הלמידה מרחוק על הישגים אקדמיים. מגמות, 55(2), 100–125.
American Psychological Association. (2020). Publication manual of the American Psychological Association (7th ed.).
"""


@pytest.fixture
def paper_text(apa_references):
    return (
        "Introduction\n"
        "Prior work (Cohen, 1988) shows power matters. Bandura and Walters (1963) argued otherwise, "
        "and prospect theory (Kahneman & Tversky, 1979; Smith et al., 2021) is relevant.\n"
        "Levi (2019) reports more. See also (American Psychological Association, 2020).\n"
        "References\n" + apa_references
    )


def make_docx(text: str) -> bytes:
    from docx import Document

    doc = Document()
    # A docx paragraph is one bibliography entry, so unwrap the PDF-style wrapped line.
    for para in text.replace("invisible\nstudents", "invisible students").split("\n"):
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in text.split("\n"):
        c.setFont("Helvetica", 6)
        c.drawString(40, y, line.encode("latin-1", "replace").decode("latin-1"))
        y -= 13
    c.save()
    return buf.getvalue()
