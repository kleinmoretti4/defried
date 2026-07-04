"""Sight-Text API: converts documents and Anki decks to dyslexia-friendly formats."""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

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

# Vercel Functions cap request bodies at ~4.5 MB, so enforce the same limit
# everywhere for consistent behavior between local dev and production.
MAX_UPLOAD_BYTES = 4 * 1024 * 1024


def _check_mode(mode: str) -> str:
    if mode not in ("partial", "full"):
        raise HTTPException(status_code=422, detail="mode must be 'partial' or 'full'")
    return mode


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (4 MB max).")
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    return data


def _inline_download(data: bytes, filename: str, media_type: str) -> dict:
    """Package a generated file directly into the JSON response.

    The app runs as a serverless function on Vercel, so files written to
    disk in one request are not reliably available to a later download
    request. Returning the bytes inline avoids any cross-request state.
    """
    return {
        "filename": filename,
        "media_type": media_type,
        "data_b64": base64.b64encode(data).decode("ascii"),
    }


def _safe_name(title: str) -> str:
    return (
        "".join(c if c.isalnum() or c in "-_ " else "" for c in title).strip()
        or "document"
    )


@app.get("/api/health")
def health() -> dict:
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

    pdf_bytes = build_pdf(blocks)
    return {
        "kind": "document",
        "mode": mode,
        "title": title,
        "blocks": blocks,
        "download": _inline_download(
            pdf_bytes,
            f"{_safe_name(title)}-dyslexia-friendly.pdf",
            "application/pdf",
        ),
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

    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "deck.apkg"
        build_apkg(new_name, cards, str(out_path))
        apkg_bytes = out_path.read_bytes()

    return {
        "kind": "anki",
        "mode": mode,
        "deck_name": new_name,
        "card_count": len(cards),
        "preview": cards[:20],
        "download": _inline_download(
            apkg_bytes,
            f"{_safe_name(Path(file.filename).stem)}-dyslexia-friendly.apkg",
            "application/octet-stream",
        ),
    }
