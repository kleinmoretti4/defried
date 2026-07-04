# Clarity: Documents through a new lens

Clarity is a web app that takes in documents (.pdf, .docx, .txt or pasted
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

A site-wide toggle switches the interface — and the downloaded PDF or
`.apkg` — to the OpenDyslexic typeface for readers who prefer it (the font
is embedded in both download formats).

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

## Deploying to Vercel

The app deploys as **two Vercel projects** from this one repo.

### 1. Backend project (FastAPI)

1. In [vercel.com/new](https://vercel.com/new), import this repo and set
   **Root Directory** to `backend`. Vercel auto-detects FastAPI (it finds
   the `app` instance at the recognized `app/main.py` entrypoint) and runs
   the whole API as a single Python function.
2. Add the `GEMINI_API_KEY` environment variable (needed for Full
   Transformation).
3. Deploy, and note the deployment URL (e.g.
   `https://clarity-api.vercel.app`).

`backend/vercel.json` sets `maxDuration: 120` so long Gemini rewrites don't
time out, and `.python-version` pins Python 3.12.

### 2. Frontend project (Next.js)

1. Import the same repo again as a second project with **Root Directory**
   set to `frontend`.
2. Add a `BACKEND_URL` environment variable pointing at the backend
   deployment URL from step 1.
3. Deploy. The Next.js rewrite proxies `/api/*` to the backend, so the
   frontend needs no other configuration.

Equivalent CLI flow:

```bash
npm i -g vercel && vercel login

cd backend
vercel link && vercel env add GEMINI_API_KEY production
vercel --prod        # note the URL

cd ../frontend
vercel link && vercel env add BACKEND_URL production   # paste backend URL
vercel --prod
```

After the first deploy, every push to `main` deploys production and every
branch push gets a preview URL automatically.

### Serverless constraints

- Uploads are capped at 4 MB (Vercel functions limit request bodies to
  ~4.5 MB). The backend and frontend both enforce this.
- Converted files are returned inline in the JSON response (base64) instead
  of being staged on disk, because serverless instances don't share a
  filesystem between requests.

## API

- `POST /api/convert/document` — form fields: `mode` (`partial` | `full`),
  and either `file` (.pdf/.docx/.txt) or `text` (pasted text). Returns the
  converted content as structured blocks plus the generated PDF inline
  (`download.data_b64`).
- `POST /api/convert/anki` — form fields: `mode` and `file` (.apkg). Returns
  deck info, a card preview and the rebuilt `.apkg` inline.
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
