# Sight-Text

Sight-Text is a web app that takes in documents (.pdf, .docx, .txt or pasted
text) and Anki decks (.apkg) and converts them to make them more dyslexia
friendly.

It offers two conversion pathways:

- **Partial Transformation** — keeps your words and changes typography,
  layout & formatting: increased letter/word/line spacing, left-align only,
  short line lengths (~66 characters) and a cream, low-glare background with
  dark navy text (WCAG-compliant contrast).
- **Full Transformation** — everything in the partial transformation, plus a
  rewritten clear content structure (active voice, consistent short
  sentences, inverted-pyramid ordering and scannable headings) using the
  Gemini API.

Documents can be read in an accessible in-browser reader or downloaded as a
reformatted PDF. Anki decks are rebuilt as a new `.apkg` with
dyslexia-friendly card styling.

## Stack

- **Frontend:** Next.js (App Router, TypeScript)
- **Backend:** Python + FastAPI
- **PDF extraction & generation:** PyMuPDF
- **Anki processing:** `zipfile` + `sqlite3` (reading `.apkg`) and `genanki`
  (rebuilding decks)
- **AI rewriting:** `google-genai` (Gemini API)

## Running locally

### 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt

# Needed for Full Transformation only:
export GEMINI_API_KEY=your-key-here

uvicorn app.main:app --port 8000
```

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The Next.js dev server proxies `/api/*` to the
backend (set `BACKEND_URL` to override the default `http://localhost:8000`).

## API

- `POST /api/convert/document` — form fields: `mode` (`partial` | `full`),
  and either `file` (.pdf/.docx/.txt) or `text` (pasted text). Returns the
  converted content as structured blocks plus a PDF download URL.
- `POST /api/convert/anki` — form fields: `mode` and `file` (.apkg). Returns
  deck info, a card preview and an `.apkg` download URL.
- `GET /api/download/{token}` — downloads a staged converted file.
- `GET /api/health` — health check; reports whether a Gemini key is
  configured.

## Notes

- Partial transformation works fully offline; only Full transformation calls
  the Gemini API (model configurable via `GEMINI_MODEL`, default
  `gemini-2.5-flash`).
- `.apkg` files exported from very new Anki versions with the newer `anki21b`
  database are not supported — re-export with "support older Anki versions"
  enabled.
- The formatting rules follow Dyslexia Scotland's "Dyslexia-friendly typed
  content" guidance: spacing over typeface, 1.5x line spacing, left
  alignment, ~50–75 character lines, cream/low-glare backgrounds, chunked
  scannable structure and short conversational sentences.
