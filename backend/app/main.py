"""Sight-Text API: converts documents and Anki decks to dyslexia-friendly formats."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from .anki import AnkiError, build_apkg, notes_to_cards, read_apkg
from .extract import ExtractionError, blocks_from_plain_text, extract_blocks
from .pdfbuild import build_pdf
from .transform import (
    GeminiError,
    full_transform_cards,
    full_transform_document,
)

app = FastAPI(title="Sight-Text API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Converted Anki decks are staged here for download, keyed by token.
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "sight-text-downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

MAX_UPLOAD_BYTES = 40 * 1024 * 1024


def _check_mode(mode: str) -> str:
    if mode not in ("partial", "full"):
        raise HTTPException(status_code=422, detail="mode must be 'partial' or 'full'")
    return mode


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (40 MB max).")
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    return data


@app.get("/api/health")
def health() -> dict:
    import os

    return {
        "status": "ok",
        "gemini_configured": bool(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        ),
    }


@app.post("/api/convert/document")
async def convert_document(
    mode: str = Form(...),
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
):
    _check_mode(mode)

    try:
        if file is not None and file.filename:
            data = await _read_upload(file)
            blocks = extract_blocks(file.filename, data)
            title = Path(file.filename).stem
        elif text and text.strip():
            blocks = blocks_from_plain_text(text)
            title = "Pasted text"
        else:
            raise HTTPException(
                status_code=422, detail="Provide a file or pasted text."
            )
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if mode == "full":
        try:
            blocks = full_transform_document(blocks)
        except GeminiError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    token = _stage_pdf(blocks, title)
    return {
        "kind": "document",
        "mode": mode,
        "title": title,
        "blocks": blocks,
        "download_url": f"/api/download/{token}",
    }


@app.post("/api/convert/anki")
async def convert_anki(
    mode: str = Form(...),
    file: UploadFile = File(...),
):
    _check_mode(mode)
    if not file.filename or not file.filename.lower().endswith(".apkg"):
        raise HTTPException(
            status_code=422, detail="Please upload an Anki deck export (.apkg)."
        )

    data = await _read_upload(file)
    try:
        parsed = read_apkg(data)
        cards = notes_to_cards(parsed)
    except AnkiError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if mode == "full":
        try:
            cards = full_transform_cards(cards)
        except GeminiError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    deck_name = next(
        (n for n in parsed["decks"].values() if n.lower() != "default"),
        Path(file.filename).stem,
    )
    new_name = f"{deck_name} (dyslexia friendly)"

    token = uuid.uuid4().hex
    out_path = DOWNLOAD_DIR / f"{token}.apkg"
    build_apkg(new_name, cards, str(out_path))
    (DOWNLOAD_DIR / f"{token}.name").write_text(f"{Path(file.filename).stem}-dyslexia-friendly.apkg")

    return {
        "kind": "anki",
        "mode": mode,
        "deck_name": new_name,
        "card_count": len(cards),
        "preview": cards[:20],
        "download_url": f"/api/download/{token}",
    }


def _stage_pdf(blocks: list[dict], title: str) -> str:
    token = uuid.uuid4().hex
    pdf_bytes = build_pdf(blocks)
    (DOWNLOAD_DIR / f"{token}.pdf").write_bytes(pdf_bytes)
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in title).strip() or "document"
    (DOWNLOAD_DIR / f"{token}.name").write_text(f"{safe}-dyslexia-friendly.pdf")
    return token


@app.get("/api/download/{token}")
def download(token: str):
    if not token.isalnum():
        raise HTTPException(status_code=404, detail="Not found.")
    for suffix, media_type in (
        (".apkg", "application/octet-stream"),
        (".pdf", "application/pdf"),
    ):
        path = DOWNLOAD_DIR / f"{token}{suffix}"
        if path.exists():
            name_file = DOWNLOAD_DIR / f"{token}.name"
            filename = (
                name_file.read_text().strip()
                if name_file.exists()
                else f"sight-text{suffix}"
            )
            return FileResponse(path, media_type=media_type, filename=filename)
    raise HTTPException(status_code=404, detail="Download expired or not found.")
