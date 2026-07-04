"use client";

import { useCallback, useRef, useState } from "react";
import styles from "./page.module.css";

type Source = "document" | "anki";
type Mode = "partial" | "full";
type Stage = "landing" | "pathway" | "input" | "working" | "result";

type Block = {
  type: "heading" | "subheading" | "paragraph" | "list" | "key";
  text?: string;
  items?: string[];
};

type DocumentResult = {
  kind: "document";
  mode: Mode;
  title: string;
  blocks: Block[];
  download_url: string;
};

type AnkiResult = {
  kind: "anki";
  mode: Mode;
  deck_name: string;
  card_count: number;
  preview: { front: string; back: string }[];
  download_url: string;
};

type Result = DocumentResult | AnkiResult;

const SAMPLE_TEXT = `Photosynthesis

Photosynthesis is the process by which green plants and some other organisms use sunlight to synthesize foods from carbon dioxide and water. It is generally considered that oxygen is released as a by-product of this process.

Light-dependent reactions are carried out in the thylakoid membranes of the chloroplasts, where light energy is converted by chlorophyll into chemical energy, which is then utilised in the light-independent reactions taking place in the stroma, in which carbon dioxide is fixed into glucose.`;

export default function Home() {
  const [stage, setStage] = useState<Stage>("landing");
  const [source, setSource] = useState<Source>("document");
  const [mode, setMode] = useState<Mode>("partial");
  const [file, setFile] = useState<File | null>(null);
  const [pastedText, setPastedText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [showHow, setShowHow] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const openPathway = (src: Source) => {
    setSource(src);
    setError(null);
    setStage("pathway");
  };

  const choosePathway = (m: Mode) => {
    setMode(m);
    setStage("input");
  };

  const reset = () => {
    setStage("landing");
    setFile(null);
    setPastedText("");
    setResult(null);
    setError(null);
  };

  const convert = useCallback(async () => {
    setError(null);
    if (source === "anki" && !file) {
      setError("Please choose a .apkg file first.");
      return;
    }
    if (source === "document" && !file && !pastedText.trim()) {
      setError("Please choose a file or paste some text first.");
      return;
    }
    setStage("working");
    try {
      const form = new FormData();
      form.append("mode", mode);
      if (file) form.append("file", file);
      if (source === "document" && !file) form.append("text", pastedText);

      const endpoint =
        source === "anki" ? "/api/convert/anki" : "/api/convert/document";
      const res = await fetch(endpoint, { method: "POST", body: form });
      if (!res.ok) {
        let detail = `Conversion failed (HTTP ${res.status}).`;
        try {
          const data = await res.json();
          if (data.detail) detail = String(data.detail);
        } catch {
          /* keep default message */
        }
        throw new Error(detail);
      }
      const data: Result = await res.json();
      setResult(data);
      setStage("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setStage("input");
    }
  }, [source, mode, file, pastedText]);

  const runDemo = () => {
    setSource("document");
    setFile(null);
    setPastedText(SAMPLE_TEXT);
    setError(null);
    setStage("pathway");
  };

  const accept = source === "anki" ? ".apkg" : ".pdf,.doc,.docx,.txt";

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title} onClick={reset}>
          SIGHT-TEXT
        </h1>
        <p className={styles.tagline}>
          Sight-text is a tool that takes in documents and converts them to
          make them more dyslexia friendly{" "}
          <span aria-hidden="true">🤌</span>
        </p>
      </header>

      <main className={styles.main}>
        {stage === "landing" && (
          <div className={styles.cardRow}>
            <button
              className={styles.bigCard}
              onClick={() => openPathway("document")}
            >
              <span className={styles.cardTitle}>
                Paste text or import document to make it dyslexia friendly
                <br />
                !!!
              </span>
              <span className={styles.cardNote}>
                supported file types: .pdf, .doc &amp; .txt,
              </span>
            </button>
            <button
              className={styles.bigCard}
              onClick={() => openPathway("anki")}
            >
              <span className={styles.cardTitle}>
                Import your Anki flashcards to make it dyslexia friendly
                <br />
                !!!
              </span>
              <span className={styles.cardNote}>
                supported file types: .apkg (anki deck export)
              </span>
            </button>
          </div>
        )}

        {stage === "pathway" && (
          <>
            <div className={styles.cardRow} aria-hidden="true">
              <div className={`${styles.bigCard} ${styles.dimmed}`}>
                <span className={styles.cardTitle}>
                  Paste text or import document to make it dyslexia friendly
                </span>
              </div>
              <div className={`${styles.bigCard} ${styles.dimmed}`}>
                <span className={styles.cardTitle}>
                  Import your Anki flashcards to make it dyslexia friendly
                </span>
              </div>
            </div>
            <div className={styles.overlay} onClick={() => setStage("landing")}>
              <div
                className={styles.pathwayModal}
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-label="Select pathway"
              >
                <h2 className={styles.pathwayTitle}>SELECT PATHWAY</h2>
                <button
                  className={styles.pathwayOption}
                  onClick={() => choosePathway("partial")}
                >
                  <b>. Partial Transformation:</b> Changes typography, layout
                  &amp; formatting (spacing, left-align only), line length, and
                  background contrast
                </button>
                <button
                  className={styles.pathwayOption}
                  onClick={() => choosePathway("full")}
                >
                  <b>. Full Transformation:</b> Everything in partial
                  transformation but with a rewritten clear content structure
                  (active voice, consist sentences, and scannability) using the
                  gemini api
                </button>
              </div>
            </div>
          </>
        )}

        {stage === "input" && (
          <div className={styles.panel}>
            <h2 className={styles.panelTitle}>
              {source === "anki" ? "IMPORT ANKI DECK" : "IMPORT DOCUMENT"}{" "}
              <span className={styles.modeBadge}>
                {mode === "full" ? "full transformation" : "partial transformation"}
              </span>
            </h2>

            <div
              className={styles.dropzone}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const dropped = e.dataTransfer.files?.[0];
                if (dropped) setFile(dropped);
              }}
            >
              {file ? (
                <>
                  <span>{file.name}</span>
                  <button
                    className={styles.smallButton}
                    onClick={(e) => {
                      e.stopPropagation();
                      setFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                  >
                    remove
                  </button>
                </>
              ) : (
                <span>
                  drop a file here or click to browse ({accept.replaceAll(",", " ")})
                </span>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept={accept}
                hidden
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>

            {source === "document" && (
              <>
                <p className={styles.orLine}>— or paste text —</p>
                <textarea
                  className={styles.textarea}
                  rows={8}
                  placeholder="paste your text here..."
                  value={pastedText}
                  onChange={(e) => setPastedText(e.target.value)}
                />
              </>
            )}

            {error && <p className={styles.error}>{error}</p>}

            <div className={styles.buttonRow}>
              <button className={styles.actionButton} onClick={convert}>
                CONVERT
              </button>
              <button className={styles.ghostButton} onClick={reset}>
                cancel
              </button>
            </div>
          </div>
        )}

        {stage === "working" && (
          <div className={styles.panel}>
            <p className={styles.working}>
              converting
              <span className={styles.blink}>_</span>
            </p>
            <p className={styles.workingNote}>
              {mode === "full"
                ? "rewriting content with gemini, this can take a little while..."
                : "reformatting your content..."}
            </p>
          </div>
        )}

        {stage === "result" && result?.kind === "document" && (
          <div className={styles.resultWrap}>
            <div className={styles.resultBar}>
              <span>
                {result.title} · {result.mode} transformation
              </span>
              <span className={styles.resultActions}>
                <a
                  className={styles.actionButton}
                  href={result.download_url}
                  download
                >
                  DOWNLOAD PDF
                </a>
                <button className={styles.ghostButton} onClick={reset}>
                  start over
                </button>
              </span>
            </div>
            <article className={styles.reader}>
              {result.blocks.map((block, i) => {
                switch (block.type) {
                  case "heading":
                    return <h2 key={i}>{block.text}</h2>;
                  case "subheading":
                    return <h3 key={i}>{block.text}</h3>;
                  case "key":
                    return (
                      <p key={i} className={styles.keyBlock}>
                        {block.text}
                      </p>
                    );
                  case "list":
                    return (
                      <ul key={i}>
                        {block.items?.map((item, j) => (
                          <li key={j}>{item}</li>
                        ))}
                      </ul>
                    );
                  default:
                    return <p key={i}>{block.text}</p>;
                }
              })}
            </article>
          </div>
        )}

        {stage === "result" && result?.kind === "anki" && (
          <div className={styles.resultWrap}>
            <div className={styles.resultBar}>
              <span>
                {result.deck_name} · {result.card_count} cards ·{" "}
                {result.mode} transformation
              </span>
              <span className={styles.resultActions}>
                <a
                  className={styles.actionButton}
                  href={result.download_url}
                  download
                >
                  DOWNLOAD .APKG
                </a>
                <button className={styles.ghostButton} onClick={reset}>
                  start over
                </button>
              </span>
            </div>
            <p className={styles.previewLabel}>
              preview (first {result.preview.length} cards):
            </p>
            <div className={styles.cardPreviewList}>
              {result.preview.map((card, i) => (
                <div key={i} className={styles.flashcard}>
                  <div className={styles.flashFront}>{card.front}</div>
                  {card.back && (
                    <div className={styles.flashBack}>{card.back}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      <footer className={styles.footer}>
        <a href="mailto:hello@sight-text.example">Contact</a>
        <button className={styles.footerLink} onClick={() => setShowHow(true)}>
          How it works
        </button>
        <button className={styles.footerLink} onClick={runDemo}>
          demo
        </button>
      </footer>

      {showHow && (
        <div className={styles.overlay} onClick={() => setShowHow(false)}>
          <div
            className={styles.pathwayModal}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="How it works"
          >
            <h2 className={styles.pathwayTitle}>HOW IT WORKS</h2>
            <p className={styles.howText}>
              1. Import a document (.pdf, .docx, .txt), paste text, or import an
              Anki deck (.apkg).
            </p>
            <p className={styles.howText}>
              2. Pick a pathway. <b>Partial</b> keeps your words and fixes the
              formatting: more letter, word and line spacing, left-aligned
              text, short line lengths (~66 characters) and a cream, low-glare
              background. <b>Full</b> also rewrites the content with the Gemini
              API: active voice, sentences under 25 words, inverted-pyramid
              structure and scannable headings.
            </p>
            <p className={styles.howText}>
              3. Read the result in the accessible reader, or download it as a
              dyslexia-friendly PDF or Anki deck.
            </p>
            <button
              className={styles.actionButton}
              onClick={() => setShowHow(false)}
            >
              close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
