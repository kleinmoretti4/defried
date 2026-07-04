"""Text extraction from uploaded documents (.pdf, .txt, .doc/.docx)."""

from __future__ import annotations

import io
import re
import statistics

import fitz  # PyMuPDF


class ExtractionError(Exception):
    pass


def extract_blocks_from_pdf(data: bytes) -> list[dict]:
    """Extract text from a PDF as a list of blocks.

    Uses font-size heuristics to tell headings apart from body text:
    spans that are noticeably larger than the document's median font size
    are treated as headings.
    """
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ExtractionError(f"Could not open PDF: {exc}") from exc

    # First pass: collect font sizes of all text spans to find the body size.
    sizes: list[float] = []
    pages: list[list[dict]] = []
    for page in doc:
        page_dict = page.get_text("dict")
        page_blocks = []
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            lines = []
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(s.get("text", "") for s in spans)
                if not text.strip():
                    continue
                span_sizes = [s.get("size", 0) for s in spans if s.get("text", "").strip()]
                size = max(span_sizes) if span_sizes else 0
                sizes.append(size)
                lines.append({"text": text, "size": size})
            if lines:
                page_blocks.append(lines)
        pages.append(page_blocks)
    doc.close()

    if not sizes:
        raise ExtractionError(
            "No selectable text found in this PDF. It may be a scanned image."
        )

    body_size = statistics.median(sizes)
    heading_threshold = body_size * 1.15

    blocks: list[dict] = []
    for page_blocks in pages:
        for lines in page_blocks:
            # Group consecutive lines of the same kind (heading vs body).
            current_kind = None
            current_parts: list[str] = []

            def flush():
                nonlocal current_parts, current_kind
                if current_parts:
                    text = _join_lines(current_parts)
                    if text:
                        blocks.append(
                            {"type": current_kind or "paragraph", "text": text}
                        )
                current_parts = []

            for line in lines:
                kind = "heading" if line["size"] >= heading_threshold else "paragraph"
                if kind != current_kind:
                    flush()
                    current_kind = kind
                current_parts.append(line["text"])
            flush()

    return _merge_blocks(blocks)


def extract_blocks_from_txt(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    return blocks_from_plain_text(text)


def extract_blocks_from_docx(data: bytes) -> list[dict]:
    try:
        from docx import Document
    except ImportError as exc:
        raise ExtractionError("python-docx is not installed") from exc
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError(
            f"Could not open Word document (legacy .doc files are not supported, "
            f"please save as .docx or PDF): {exc}"
        ) from exc

    blocks: list[dict] = []
    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower() if para.style else ""
        kind = "heading" if style.startswith("heading") or style == "title" else "paragraph"
        blocks.append({"type": kind, "text": text})
    if not blocks:
        raise ExtractionError("No text found in this Word document.")
    return blocks


def blocks_from_plain_text(text: str) -> list[dict]:
    """Split pasted/plain text into paragraph blocks on blank lines."""
    blocks: list[dict] = []
    for chunk in re.split(r"\n\s*\n", text):
        chunk = _join_lines(chunk.splitlines())
        if not chunk:
            continue
        # A short single line without ending punctuation reads like a heading.
        is_heading = len(chunk) <= 70 and not re.search(r"[.!?:;,]$", chunk) and "\n" not in chunk
        blocks.append({"type": "heading" if is_heading else "paragraph", "text": chunk})
    if not blocks:
        raise ExtractionError("No text found.")
    return blocks


def extract_blocks(filename: str, data: bytes) -> list[dict]:
    name = filename.lower()
    if name.endswith(".pdf"):
        return extract_blocks_from_pdf(data)
    if name.endswith(".txt"):
        return extract_blocks_from_txt(data)
    if name.endswith((".docx", ".doc")):
        return extract_blocks_from_docx(data)
    raise ExtractionError(
        "Unsupported file type. Supported types: .pdf, .docx, .doc and .txt"
    )


def _join_lines(lines: list[str]) -> str:
    """Join hard-wrapped lines back into flowing text, fixing hyphenation."""
    out = ""
    for raw in lines:
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if out.endswith("-") and line and line[0].islower():
            out = out[:-1] + line  # de-hyphenate words split across lines
        elif out:
            out += " " + line
        else:
            out = line
    # Strip bullet glyphs left over from PDF extraction.
    out = re.sub(r"^[•▪●◦‣·*]\s*", "", out)
    return out.strip()


def _merge_blocks(blocks: list[dict]) -> list[dict]:
    """Merge fragments split across lines/pages and drop page-number noise."""
    merged: list[dict] = []
    for block in blocks:
        text = block["text"].strip()
        if not text:
            continue
        if re.fullmatch(r"(page\s*)?\d{1,4}(\s*of\s*\d{1,4})?", text, re.IGNORECASE):
            continue  # page numbers
        prev = merged[-1] if merged else None
        if prev and prev["type"] == "heading" and block["type"] == "heading":
            prev["text"] += " " + text
        elif (
            prev
            and prev["type"] == "paragraph"
            and block["type"] == "paragraph"
            and _continues_sentence(prev["text"], text)
        ):
            if prev["text"].endswith("-") and text[0].islower():
                prev["text"] = prev["text"][:-1] + text
            else:
                prev["text"] += " " + text
        else:
            merged.append({"type": block["type"], "text": text})
    return merged


def _continues_sentence(previous: str, current: str) -> bool:
    """True when `current` looks like the continuation of `previous`."""
    if re.search(r"[.!?:;]$", previous):
        return False
    return current[0].islower() or previous.endswith((",", "-")) or (
        previous[-1].isalpha() and len(previous.split()) >= 4
    )
