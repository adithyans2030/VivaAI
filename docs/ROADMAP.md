# Roadmap

Work that is intentionally deferred or not yet built, measured against the original product spec.
Items are grouped by priority. Everything not listed here is implemented and covered by tests.

## Next (planned)

| Item | Why it matters |
|---|---|
| **Authenticity calibration on real labelled recordings** | Weights and thresholds are hand-set and unvalidated. See [authenticity-methodology.md](authenticity-methodology.md#4-calibration-current-status). |

## Spec features not yet built

| Item | Current state |
|---|---|
| Silero VAD (`@ricky0123/vad-web`) | End of speech is detected with a simple volume threshold (1.8 s of quiet), which is less robust to background noise. |
| Server-side `partial_transcript` | Live captions use the browser's own speech recognition where available. |
| Sentence-by-sentence LLM → TTS streaming | Question audio is synthesised whole. The < 4 s end-of-answer-to-next-question target has **not been measured** on the target GPU. |
| Per-stage latency metrics (STT / LLM / TTS) | Only total request time (`X-Process-Time-Ms`) is recorded. |
| GPU job queue for concurrent sessions | Each session calls models directly; concurrent load has not been tested. |
| Hybrid retrieval (dense + keyword fused) and reranking | `HybridRAGStore` uses dense (Chroma) search, and falls back to keyword overlap only when Chroma is unavailable or returns nothing. The two are not combined, and there is no reranker. |
| Kokoro TTS | Accepted by config but falls back to browser speech (with a warning). Piper and EdgeTTS work. |
| Class analytics: score distribution, weak topics, per-student trends | The analytics page shows averages and counts (overall and per subject) only. |
| Session list filters for date and score | Search plus authenticity-flag filter only. |
| Student UI for data export/deletion | Available via API only (`/auth/me/export-data`, `/auth/me/delete-account-data`). |
| Automatic expiry of transcripts and reports | Only audio is purged automatically. |
| Playwright end-to-end tests in CI | Browser flows have been verified manually with a Playwright script, but no browser test runs in CI yet. |
| Docker GPU profile verified end to end | Compose file exists; not re-verified after recent changes. |
| shadcn/ui, Framer Motion, Recharts | The UI uses custom Tailwind components instead. |

## Recently completed

- Browser session moved from `localStorage` tokens to httpOnly cookies with a CSRF header check.
- WebSocket accepts single-use tickets only (the `?token=` fallback is gone).
- Prompt-injection flags log the turn ID instead of the student's words.
- Alembic migrations (`backend/alembic/`), applied automatically at startup; pre-migration databases are adopted without data loss.
- PDF export of session reports.
- Refresh-token revocation, WebSocket tickets and rate limits moved from process memory into the database.

## Clean-up

- Merge the two seed scripts (`seed.py`: admin plus simple accounts; `seed_demo.py`: demo data without an admin).
- PDF reports use DejaVu (Docker) or Arial (Windows), which have no Devanagari glyphs; Hindi text needs `PDF_FONT_PATH` pointing at e.g. Noto Sans Devanagari. Consider bundling a font and fpdf2 fallback fonts.
- `EMBEDDING_MODEL` is not used: ChromaDB embeds with its built-in all-MiniLM-L6-v2. Wire the setting through a
  Chroma embedding function (e.g. `bge-small-en-v1.5`) or remove it.
- Retrieval returns the top-k chunks even when they are barely related (similarity ≈ 0.25); add a minimum
  relevance threshold so weak matches are not cited as sources.
- Deleting a subject removes its vectors but leaves an empty Chroma collection; drop the collection too.
- Delete the outdated duplicate `backend/scripts/calibrate_authenticity.py` (the maintained one is `app/scripts/`).
- Collapse the duplicate audio route (`/audio/{session}/{turn}` and `/sessions/{session}/turns/{turn}/audio`).
