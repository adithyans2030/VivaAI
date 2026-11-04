# VivaIQ Architecture

## 1. System overview

```
Browser (Next.js)
  ├─ REST (fetch, bearer JWT) ───────────────►  FastAPI  /api/v1
  └─ WebSocket (single-use ticket) ──────────►  /api/v1/ws/sessions/{id}
                                                   │
          ┌──────────────┬──────────────┬──────────┼─────────────┬──────────────┐
          ▼              ▼              ▼          ▼             ▼              ▼
         STT            RAG        LLM gateway    TTS      Authenticity    SQL + files
   faster-whisper    ChromaDB +    Ollama │ Gemini │  Edge │ Piper │   analyzer     SQLite/Postgres,
   (word stamps)     embeddings    Grok │ Mock       Browser       (advisory)     audio, documents
```

One viva turn:

1. The **examiner** retrieves context for an uncovered topic from the subject's Chroma collection and asks
   the LLM for a question (type and difficulty adapt to previous scores).
2. **TTS** synthesises it (or the browser speaks it); the browser plays it, then records the answer with
   `MediaRecorder`, streaming `audio_chunk`s.
3. On `speech_end` the audio is transcoded (ffmpeg → 16 kHz WAV), stored, and transcribed by **Whisper**
   with word timestamps.
4. The **grader** scores the transcript against the retrieved context using the rubric (strict JSON,
   validated by Pydantic, one repair attempt on bad JSON).
5. The **authenticity analyzer** computes advisory signals, relative to the warm-up baseline.
6. Results are saved on the `Turn` row and sent as `feedback`; the client asks for the next question.

Protocol details: [websocket-protocol.md](websocket-protocol.md). REST: [api-reference.md](api-reference.md).

## 2. Backend (`backend/app`)

| Package | Responsibility |
|---|---|
| `core/` | Settings (Pydantic `BaseSettings`, startup validation), DB engine, JWT/tickets/rate limits, logging, errors |
| `api/` | Thin REST routers; access rules in `deps.py` (`require_role`, `ensure_session_access`, `ensure_subject_owner`) |
| `ws/` | WebSocket handler and connection manager (buffers, one connection per session) |
| `services/` | All business logic: `examiner`, `grader`, `session_state` (orchestrator), `authenticity`, `rag`, `stt`, `tts`, `llm/`, `retention`, `audio_conversion`, `auth_state` (revocation, tickets, rate limits), `report_pdf` |
| `models/`, `schemas/` | SQLAlchemy 2 models and Pydantic v2 schemas |
| `prompts/v1/` | Versioned prompt templates; the version is stored on every turn |
| `scripts/` | Seeding and authenticity calibration |

**Provider pattern.** LLM, STT and TTS each have an abstract base and implementations chosen by config
(`LLM_PROVIDER`, `STT_PROVIDER`, `TTS_PROVIDER`). Switching Ollama → Gemini is a config change only.
LLM providers share retry-with-backoff and support JSON mode and token streaming. Mock providers exist for
tests and demos and are refused outside `DEMO_MODE`/testing.

**Background work.** Document ingestion runs as an asyncio task after upload; parsing, chunking and embedding run
in worker threads so live vivas stay responsive. At startup the backend indexes any completed document missing from
ChromaDB (e.g. uploaded while Chroma was unavailable). A maintenance sweep runs at startup and every 24 h: it
deletes expired audio and purges stale auth-state rows. Whisper inference runs in a worker thread so it doesn't block the event loop.

**Data.** SQLite by default (`DATABASE_URL` can point at PostgreSQL). The schema is managed by **Alembic**
(`backend/alembic/versions/`); the server applies pending migrations at startup, and a database created before
migrations existed is recognised and stamped at the matching revision, so no data is lost. Tests use `create_all`
on throwaway databases. Files live under `DATA_DIR` (`audio/`, `documents/`, `chromadb/`).

## 3. Frontend (`frontend/`)

| Path | Role |
|---|---|
| `app/login`, `app/student`, `app/teacher`, `app/page.tsx` | Pages (App Router, client components) |
| `lib/api.ts` | REST client: token storage, automatic refresh-and-retry on 401, authenticated blob downloads |
| `lib/ws.ts` | Typed WebSocket client: heartbeat, exponential-backoff reconnect with a fresh ticket |
| `lib/audio-recorder.ts` | Mic capture, level meter, volume-based end-of-speech detection, ordered chunk flushing |
| `components/` | Audio orb, mic-check/consent dialog, navbar (role-aware), theme provider, UI primitives |

Theming uses CSS custom properties with light and dark token sets (`app/globals.css`); fonts are self-hosted
via `next/font`.

## 4. Hardware sizing (4 GB GPU, e.g. GTX 1650)

| Component | Choice | Approx. memory |
|---|---|---|
| STT | `faster-whisper` `base.en` / `distil-small.en`, float16 (int8 on CPU) | < 1 GB VRAM |
| LLM | Ollama `qwen2.5:3b` or `gemma2:2b` (4-bit), or a cloud provider (no VRAM) | ≈ 2 GB VRAM |
| Embeddings | ChromaDB's built-in ONNX `all-MiniLM-L6-v2` (CPU) | ≈ 100 MB RAM |
| TTS | Browser, EdgeTTS (cloud) or Piper (CPU) | none on GPU |

Larger models (`large-v3`, 8B+ LLMs) need more VRAM; all sizes are environment variables. End-to-end latency
on the target GPU has not been measured yet (see [ROADMAP.md](ROADMAP.md)).

## 5. Related documents

- [Authenticity methodology & limitations](authenticity-methodology.md)
- [Security](security.md) · [Privacy & retention](privacy-and-retention.md)
- [Runbook & demo script](runbook.md) · [Roadmap](ROADMAP.md)
