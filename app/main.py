"""FastAPI app: upload a paper, stream back reference-verification results."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import lookup
from .bibliography import extract_references
from .checker import check_reference
from .extract import UnsupportedFile, extract_text
from .intext import cross_check

MAX_BYTES = 20 * 1024 * 1024
CONCURRENCY = 4
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Seminar Reference Checker")
# Overridable in tests so no real network calls are made.
client_factory = lookup.make_client


def _line(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode()


@app.post("/api/check")
async def check(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 20 MB.")
    try:
        text = extract_text(data, file.filename or "")
    except UnsupportedFile as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # corrupt or password-protected file
        raise HTTPException(422, f"Could not read the file: {exc}") from exc

    body, refs, found_section = extract_references(text)

    async def stream():
        yield _line(
            {
                "type": "parsed",
                "filename": file.filename,
                "bibliography_found": found_section,
                "references": [r.to_dict() for r in refs],
                "intext": cross_check(body, refs) if found_section else None,
            }
        )
        sem = asyncio.Semaphore(CONCURRENCY)
        async with client_factory() as client:

            async def one(ref):
                async with sem:
                    try:
                        return await check_reference(client, ref)
                    except Exception as exc:  # never let one entry kill the run
                        return {
                            "index": ref.index, "status": "error", "score": 0, "match": None,
                            "match_is_closest_only": False, "notes": [f"Unexpected error: {exc}"],
                            "scholar_url": lookup.scholar_url(ref.title or ref.raw),
                        }

            for fut in asyncio.as_completed([one(r) for r in refs]):
                yield _line({"type": "result", **await fut})
        yield _line({"type": "done"})

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
