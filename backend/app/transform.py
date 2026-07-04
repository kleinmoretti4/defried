"""Content transformations.

Partial transformation is handled by structure/formatting only (the frontend
and the rebuilt Anki deck apply the dyslexia-friendly typography). The full
transformation additionally rewrites the content with the Gemini API for
clear structure: active voice, short consistent sentences and scannability.
"""

from __future__ import annotations

import json
import os
import re


class GeminiError(Exception):
    pass


GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiError(
            "GEMINI_API_KEY is not set on the server. Full transformation needs "
            "a Gemini API key; partial transformation works without one."
        )
    try:
        from google import genai
    except ImportError as exc:
        raise GeminiError("The google-genai package is not installed.") from exc
    return genai.Client(api_key=api_key)


DOCUMENT_PROMPT = """\
You are rewriting a document to make it easier to read for people with
dyslexia. Follow these rules strictly:

- Use ACTIVE voice everywhere.
- Keep sentences short and consistent: at most 25 words per sentence.
- Keep paragraphs short: at most 5 lines (roughly 60 words).
- Use the inverted pyramid: start each section with the most important
  information ("need to know"), then supporting details, then "nice to know".
- Make the content scannable: clear headings, short chunks, and bullet lists
  where they help.
- Write conversationally, as if explaining to a friend. Avoid jargon.
- Do NOT invent information. Preserve all facts from the original.

Return ONLY a JSON array of blocks, no markdown fences, in reading order.
Each block is an object with:
  "type": one of "heading", "subheading", "paragraph", "list", "key"
  "text": string (for heading/subheading/paragraph/key)
  "items": array of strings (for list only)
Use "key" for a single, especially important takeaway sentence that should be
visually distinct.

Here is the document to rewrite:

{content}
"""

ANKI_PROMPT = """\
You are rewriting flashcards to make them easier to read for people with
dyslexia. Follow these rules strictly for every card:

- Use ACTIVE voice.
- Keep sentences short: at most 25 words each.
- Put the most important information first.
- Write conversationally and avoid jargon.
- Break long answers into short lines or simple bullet points (use "- " for
  bullets, plain text only, no HTML or markdown headers).
- Do NOT invent information, do NOT drop facts, and do NOT change what the
  card is testing. Keep cloze markers like {{{{c1::...}}}} intact if present.

Return ONLY a JSON array, no markdown fences, with one object per input card,
in the same order:
  {{"front": "...", "back": "..."}}

Here are the cards as a JSON array:

{content}
"""


def _call_gemini(prompt: str) -> str:
    client = _get_client()
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
    except Exception as exc:
        raise GeminiError(f"Gemini API request failed: {exc}") from exc
    text = getattr(response, "text", None)
    if not text:
        raise GeminiError("Gemini returned an empty response.")
    return text


def _parse_json_reply(text: str):
    """Parse Gemini's reply, tolerating stray markdown fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise GeminiError("Could not parse Gemini's response as JSON.")


def blocks_to_text(blocks: list[dict]) -> str:
    parts = []
    for block in blocks:
        if block["type"] == "heading":
            parts.append(f"# {block['text']}")
        else:
            parts.append(block["text"])
    return "\n\n".join(parts)


VALID_BLOCK_TYPES = {"heading", "subheading", "paragraph", "list", "key"}


def full_transform_document(blocks: list[dict]) -> list[dict]:
    """Rewrite document blocks with Gemini for clear content structure."""
    content = blocks_to_text(blocks)
    reply = _call_gemini(DOCUMENT_PROMPT.format(content=content))
    data = _parse_json_reply(reply)
    if not isinstance(data, list):
        raise GeminiError("Gemini did not return a list of blocks.")

    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        btype = item.get("type")
        if btype not in VALID_BLOCK_TYPES:
            btype = "paragraph"
        if btype == "list":
            items = [str(i).strip() for i in item.get("items", []) if str(i).strip()]
            if items:
                out.append({"type": "list", "items": items})
        else:
            text = str(item.get("text", "")).strip()
            if text:
                out.append({"type": btype, "text": text})
    if not out:
        raise GeminiError("Gemini returned no usable content.")
    return out


def full_transform_cards(cards: list[dict], batch_size: int = 40) -> list[dict]:
    """Rewrite flashcards with Gemini, in batches to keep prompts small."""
    out: list[dict] = []
    for start in range(0, len(cards), batch_size):
        batch = cards[start : start + batch_size]
        payload = json.dumps(
            [{"front": c["front"], "back": c["back"]} for c in batch],
            ensure_ascii=False,
        )
        reply = _call_gemini(ANKI_PROMPT.format(content=payload))
        data = _parse_json_reply(reply)
        if not isinstance(data, list):
            raise GeminiError("Gemini did not return a list of cards.")
        for original, rewritten in zip(batch, data):
            if isinstance(rewritten, dict) and str(rewritten.get("front", "")).strip():
                out.append(
                    {
                        "front": str(rewritten.get("front", "")).strip(),
                        "back": str(rewritten.get("back", "")).strip(),
                    }
                )
            else:
                out.append(original)
        # If Gemini returned fewer cards than sent, keep originals for the rest.
        if len(data) < len(batch):
            out.extend(batch[len(data):])
    return out
