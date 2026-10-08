# Seminar Reference Checker

A small local web tool for grading seminar papers. Upload a student paper (PDF or DOCX); it
finds the bibliography, looks every reference up in **Crossref**, **OpenAlex** and
**Semantic Scholar**, and shows which references it could not find online. It also checks that
in-text citations such as `(Cohen, 1988)` match the bibliography, in both directions.

Nothing is stored: the uploaded file is read in memory and discarded.

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Open <http://localhost:8000>, choose a paper, and click **Check references**.

Optional environment variables (both improve rate limits and are polite to the free APIs):

- `CONTACT_EMAIL` — sent to Crossref/OpenAlex as the "polite pool" contact.
- `S2_API_KEY` — Semantic Scholar API key, if you have one.

## What the statuses mean

| Status | Meaning |
|---|---|
| **Found** | A record with a matching title, plausible year and authors exists (or the DOI resolves to the cited paper). |
| **Likely match** | The title is close but something differs (year, authors, partial title, or the DOI points elsewhere). Worth a look: sloppy or invented details. |
| **Not found** | No sufficiently similar record. This does **not** prove fabrication. Books, theses, reports and Hebrew-language sources are often absent from these databases. |
| **Lookup error** | The databases could not be reached; try again. |

Every reference has a **Google Scholar** link for a manual check. Google Scholar is not queried
automatically because it has no API and blocks automated access.

## Limitations

- Parsing is rule-based and tuned for **APA**; unusual styles may be split or parsed wrongly.
- **Hebrew**: DOCX files work best. Some PDFs store Hebrew in visual order; the tool tries to
  detect and repair this, but check the parsed entries if a Hebrew PDF looks wrong. Hebrew
  sources are poorly covered by the databases, so expect many "not found" results there.
- In-text citation detection is approximate.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Tests use mocked database responses, so they run offline.

## Layout

- `app/extract.py` — PDF/DOCX → text
- `app/bibliography.py` — find and parse reference entries
- `app/intext.py` — in-text citation cross-check
- `app/lookup.py` — Crossref / OpenAlex / Semantic Scholar clients
- `app/matching.py`, `app/checker.py` — compare and judge matches
- `app/main.py`, `app/static/index.html` — API and web page
