"""Anki .apkg processing: read with zipfile + sqlite3, rebuild with genanki."""

from __future__ import annotations

import html
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import genanki

# Field separator used inside Anki's notes.flds column.
FIELD_SEP = "\x1f"


class AnkiError(Exception):
    pass


def read_apkg(data: bytes) -> dict:
    """Extract decks, note models and notes from an .apkg file.

    An .apkg is a zip archive containing an SQLite database
    (collection.anki2 or collection.anki21).
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        apkg_path = tmp_path / "deck.apkg"
        apkg_path.write_bytes(data)

        try:
            with zipfile.ZipFile(apkg_path) as zf:
                names = zf.namelist()
                db_name = next(
                    (n for n in ("collection.anki21", "collection.anki2") if n in names),
                    None,
                )
                if db_name is None:
                    raise AnkiError(
                        "This .apkg has no readable collection database. "
                        "Decks exported from very new Anki versions (anki21b) are "
                        "not supported; re-export with 'legacy support' enabled."
                    )
                zf.extract(db_name, tmp_path)
        except zipfile.BadZipFile as exc:
            raise AnkiError("This file is not a valid .apkg archive.") from exc

        con = sqlite3.connect(tmp_path / db_name)
        try:
            row = con.execute("SELECT models, decks FROM col").fetchone()
            if row is None:
                raise AnkiError("Empty Anki collection.")
            models = json.loads(row[0])
            decks = json.loads(row[1])
            note_rows = con.execute("SELECT id, mid, flds, tags FROM notes").fetchall()
            card_rows = con.execute("SELECT nid, did FROM cards").fetchall()
        finally:
            con.close()

    note_deck: dict[int, int] = {}
    for nid, did in card_rows:
        note_deck.setdefault(nid, did)

    notes = []
    for nid, mid, flds, tags in note_rows:
        model = models.get(str(mid), {})
        field_names = [f["name"] for f in model.get("flds", [])]
        values = flds.split(FIELD_SEP)
        notes.append(
            {
                "id": nid,
                "model_id": mid,
                "model_name": model.get("name", "Basic"),
                "deck_id": note_deck.get(nid),
                "field_names": field_names,
                "fields": values,
                "tags": tags.strip(),
            }
        )

    if not notes:
        raise AnkiError("No notes found in this deck.")

    deck_names = {int(k): v.get("name", "Deck") for k, v in decks.items()}
    return {"models": models, "decks": deck_names, "notes": notes}


def strip_html(value: str) -> str:
    """Convert an Anki field's HTML to plain text."""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"</(div|p|li)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\[sound:[^\]]*\]", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Card template with dyslexia-friendly styling baked in:
# cream background, dark navy text, generous letter/word/line spacing,
# left-aligned, capped line length.
DYSLEXIA_CARD_CSS = """
.card {
  font-family: Verdana, Arial, sans-serif;
  font-size: 22px;
  letter-spacing: 0.035em;
  word-spacing: 0.16em;
  line-height: 1.6;
  text-align: left;
  color: #1a2b4a;
  background-color: #faf3e0;
  padding: 24px;
  max-width: 34em;
  margin: 0 auto;
}
.question { font-weight: bold; margin-bottom: 12px; }
.answer { margin-top: 12px; }
hr#answer { border: none; border-top: 2px solid #d9c9a3; margin: 16px 0; }
"""


def _to_card_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")


def build_apkg(
    deck_name: str,
    cards: list[dict],
    output_path: str,
) -> None:
    """Build a new .apkg with dyslexia-friendly card styling.

    ``cards`` is a list of {"front": str, "back": str} dicts (plain text).
    """
    model = genanki.Model(
        1607392319,
        "Sight-Text Dyslexia Friendly",
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[
            {
                "name": "Card 1",
                "qfmt": '<div class="question">{{Front}}</div>',
                "afmt": '{{FrontSide}}<hr id="answer"><div class="answer">{{Back}}</div>',
            }
        ],
        css=DYSLEXIA_CARD_CSS,
    )

    deck = genanki.Deck(abs(hash(deck_name)) % (10**10) + 1, deck_name)
    for card in cards:
        note = genanki.Note(
            model=model,
            fields=[_to_card_html(card["front"]), _to_card_html(card["back"])],
        )
        deck.add_note(note)

    genanki.Package(deck).write_to_file(output_path)


def notes_to_cards(parsed: dict) -> list[dict]:
    """Reduce arbitrary note models to front/back plain-text pairs."""
    cards = []
    for note in parsed["notes"]:
        fields = [strip_html(f) for f in note["fields"]]
        fields = [f for f in fields if f]
        if not fields:
            continue
        front = fields[0]
        back = "\n\n".join(fields[1:]) if len(fields) > 1 else ""
        cards.append({"front": front, "back": back})
    if not cards:
        raise AnkiError("No usable text found in this deck's notes.")
    return cards
