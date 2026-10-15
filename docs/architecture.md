# VivaIQ — Architecture & System Design

## 1. System Overview & Sizing for GTX 1650 (4GB VRAM)
- **Local GPU Optimization**: Detected hardware is NVIDIA GeForce GTX 1650 (4GB VRAM). Large 14B models and `large-v3` Whisper cannot fit concurrently in 4GB VRAM.
  - **STT Strategy**: `faster-whisper` configured default to `distil-small.en` or `base.en` on CUDA (`compute_type="float16"` or `"int8"`), or `cpu` fallback. This uses < 800MB VRAM and achieves sub-second latency for voice answers.
  - **LLM Strategy**: Multi-provider architecture with:
    - `GeminiProvider` (production cloud, ultrafast, zero local VRAM cost, default recommended for low-latency voice pipeline).
    - `OllamaProvider` (local demo with `qwen2.5:3b` / `llama3.2:3b` at 4-bit quantization fitting in ~2GB VRAM).
    - `GrokProvider` (xAI API integration).
    - `MockProvider` (deterministic, instant responses for automated CI/unit tests without GPU/API keys).
  - **TTS Strategy**: High-quality Piper/Kokoro local model adapter with streaming chunk output, alongside Web Speech API client-side fallback for zero latency and minimal server load when preferred.
  - **Embeddings & Vector Store**: `sentence-transformers` with `bge-small-en-v1.5` (~130MB RAM/VRAM) + ChromaDB embedded (persistent local SQLite/parquet storage) with one collection per subject.

## 2. Backend Design Decisions
- **Framework**: FastAPI with asynchronous endpoints (`async def`), Pydantic v2 Settings & Schemas, and SQLAlchemy 2.0.
- **Database**: SQLite default for quick local demo & tests (`sqlite+aiosqlite:///./vivaiq.db`), fully switchable via `DATABASE_URL` to PostgreSQL for production.
- **Authentication & Security**:
  - Stateless JWT with Access Tokens (short-lived, 30m) & Refresh Tokens (7d).
  - Password hashing with bcrypt / argon2.
  - Role-Based Access Control (`student`, `teacher`, `admin`) via FastAPI dependency injection.
  - Mandatory session consent flag (`recording_consent: true`) logged in DB before audio streaming begins.
- **Modularity**:
  - `app/services/` holds all domain logic (STT, TTS, RAG, LLM, Examiner, Grader, Authenticity). Route handlers in `app/api/` and WebSocket handler in `app/ws/` strictly orchestrate services.
  - Dynamic provider loading based on `LLM_PROVIDER`, `STT_PROVIDER`, `TTS_PROVIDER`.

## 3. Frontend Architecture
- **Framework**: Next.js 14+ (App Router), TypeScript in strict mode, Tailwind CSS with an educational, calm palette (Slate, Deep Indigo, Emerald for correct, Amber for advisory flags).
- **Audio & VAD**: Web Audio API (`AudioContext`, `MediaStreamAudioSourceNode`) coupled with Silero VAD (`@ricky0123/vad-web`) or zero-crossing energy fallback for end-of-speech detection.
- **Real-time Protocol**: Typed WebSocket event system supporting bidirectional JSON messages (`audio_chunk`, `speech_end`, `transcript`, `question`, `tts_audio`, `state_change`).

## 4. Authenticity Analysis (Advisory & Non-Punitive)
- Evaluates 6 distinct signals:
  1. *Verbatim Overlap*: n-gram & cosine similarity against retrieved subject chunks.
  2. *Disfluency Rate*: natural conversational pauses vs. unnaturally rigid verbatim reading.
  3. *Pause Patterns*: punctuation pauses vs. mid-phrase hesitation.
  4. *Prosody*: pitch variance & energy dynamics via `librosa`/`parselmouth`.
  5. *Response Latency*: duration of silence before speech onset.
  6. *Probe Performance*: delta between standard recall answers vs. probing questions ("explain in your own words").
- Output is categorized as `low`, `medium`, or `high` reading likelihood accompanied by transparent human-readable evidence strings. Explicitly labelled as *advisory* for teacher review.

## 5. Directory Mapping
All services will reside in standard clean directories:
- `backend/` (FastAPI, Alembic, services, models, tests)
- `frontend/` (Next.js, Tailwind, components, hooks, lib)
- `data/` (subject uploads, audio recordings, Chroma collections)
- `docs/` (architecture, API spec, WebSocket protocol, authenticity guide)
