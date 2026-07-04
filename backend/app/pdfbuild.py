"""Build a dyslexia-friendly PDF from structured blocks using PyMuPDF."""

from __future__ import annotations

import fitz

PAGE_WIDTH, PAGE_HEIGHT = fitz.paper_size("a4")
MARGIN_X = 64
MARGIN_TOP = 64
MARGIN_BOTTOM = 72

BACKGROUND = (0.98, 0.953, 0.878)  # cream #faf3e0
TEXT_COLOR = (0.10, 0.17, 0.29)  # dark navy #1a2b4a
KEY_BG = (0.95, 0.88, 0.72)

BODY_SIZE = 13
LINE_FACTOR = 1.5
# Cap the text column so lines stay around 50-70 characters.
MAX_TEXT_WIDTH = 380

STYLES = {
    "heading": {"size": BODY_SIZE * 1.5, "font": "hebo", "space_before": 18, "space_after": 8},
    "subheading": {"size": BODY_SIZE * 1.2, "font": "hebo", "space_before": 14, "space_after": 6},
    "paragraph": {"size": BODY_SIZE, "font": "helv", "space_before": 0, "space_after": 10},
    "key": {"size": BODY_SIZE, "font": "hebo", "space_before": 6, "space_after": 12},
    "list_item": {"size": BODY_SIZE, "font": "helv", "space_before": 0, "space_after": 5},
}


class _Builder:
    def __init__(self) -> None:
        self.doc = fitz.open()
        self.page = None
        self.y = MARGIN_TOP
        self._new_page()

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        self.page.draw_rect(self.page.rect, color=None, fill=BACKGROUND)
        self.y = MARGIN_TOP

    def _write(self, text: str, style: dict, indent: float = 0, bg=None) -> None:
        size = style["size"]
        line_height = size * LINE_FACTOR
        width = min(MAX_TEXT_WIDTH, PAGE_WIDTH - 2 * MARGIN_X) - indent
        self.y += style["space_before"]

        # Measure required height by test-inserting into a tall rect.
        rect = fitz.Rect(
            MARGIN_X + indent, self.y, MARGIN_X + indent + width, PAGE_HEIGHT * 4
        )
        measure = fitz.Rect(rect)
        shape = self.page.new_shape()
        spare = shape.insert_textbox(
            measure,
            text,
            fontname=style["font"],
            fontsize=size,
            lineheight=LINE_FACTOR,
            color=TEXT_COLOR,
        )
        needed = measure.height - spare if spare >= 0 else line_height * 2
        # Do not commit the measuring shape; redo on the right page.
        if self.y + needed > PAGE_HEIGHT - MARGIN_BOTTOM:
            self._new_page()
            self.y += style["space_before"]
            rect = fitz.Rect(
                MARGIN_X + indent, self.y, MARGIN_X + indent + width, PAGE_HEIGHT - 10
            )

        if bg is not None:
            pad = 8
            bg_rect = fitz.Rect(
                rect.x0 - pad, self.y - pad, rect.x0 + width + pad, self.y + needed + pad
            )
            self.page.draw_rect(bg_rect, color=None, fill=bg)

        target = fitz.Rect(rect.x0, self.y, rect.x1, self.y + needed + line_height)
        self.page.insert_textbox(
            target,
            text,
            fontname=style["font"],
            fontsize=size,
            lineheight=LINE_FACTOR,
            color=TEXT_COLOR,
            align=fitz.TEXT_ALIGN_LEFT,
        )
        self.y += needed + style["space_after"]

    def add_block(self, block: dict) -> None:
        btype = block.get("type", "paragraph")
        if btype == "list":
            for item in block.get("items", []):
                self._write(f"\u2022  {item}", STYLES["list_item"], indent=10)
            self.y += 8
        elif btype == "key":
            self._write(block.get("text", ""), STYLES["key"], bg=KEY_BG)
        else:
            style = STYLES.get(btype, STYLES["paragraph"])
            self._write(block.get("text", ""), style)

    def to_bytes(self) -> bytes:
        return self.doc.tobytes()


def build_pdf(blocks: list[dict]) -> bytes:
    builder = _Builder()
    for block in blocks:
        builder.add_block(block)
    return builder.to_bytes()
