# VivaIQ: AI Voice Viva Examiner

VivaIQ runs oral (*viva voce*) examinations by voice. An AI examiner asks questions grounded in the course
material a teacher uploads, listens to the student's spoken answers, grades them against a rubric, and gives
the teacher an **advisory**, explainable signal of whether a student seems to be reading rather than answering
in their own words. Teachers review every result and make every decision.

---

## Features

- **Voice viva:** the examiner speaks each question; the student answers by microphone; end of speech is detected automatically (or press *Submit Answer*). Live captions, one repeat per question, resume after a dropped connection.
- **Grounded questions:** teachers upload PDF, DOCX, TXT or MD; questions are generated from retrieved passages, vary in type (conceptual, application, compare/contrast, what-if, probe), and adapt in difficulty.
- **Rubric grading:** correctness, completeness, clarity and depth, with missing points, incorrect claims and feedback. Strict JSON output; student speech is treated as untrusted input.
- **Advisory authenticity analysis:** text overlap with course material, disfluency, pause placement, cadence, pitch, response latency and probe performance, compared with the student's own warm-up baseline. Always shown with reasons; **never changes a score**. See the [methodology and its limitations](docs/authenticity-methodology.md).
- **Teacher dashboard:** sessions with transcripts, per-answer audio playback, rubric scores, reasons, notes, audited grade/flag overrides, PDF and CSV export, and class analytics.
- **Provider-agnostic:** Ollama (local), Gemini or Grok for the LLM; faster-whisper for speech-to-text; browser, EdgeTTS or Piper for speech. Switch by configuration only.
- **Privacy:** mandatory recording consent, per-subject teacher access, automatic deletion of recordings after 30 days, student data export and deletion.

## Quickstart (about 5 minutes, no GPU needed)

Prerequisites: Python 3.11+, Node.js 20+, ffmpeg on `PATH`.

All backend commands call the virtual environment's Python **explicitly**. A bare `uvicorn` or `python` can
silently pick up a system-wide install that lacks Whisper and ChromaDB: the app still starts, but cannot
hear students.

**Windows (PowerShell)**

```powershell
git clone <repo-url>; cd VivaAI
copy .env.example .env                            # demo profile: DEMO_MODE=true, mock models
copy frontend\.env.example frontend\.env.local

cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m app.scripts.seed        # admin + demo accounts
.\.venv\Scripts\python -m app.scripts.seed_demo   # course material + two reviewed vivas
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000

# new terminal
cd frontend; npm install; npm run dev
```

**Linux / macOS**

```bash
git clone <repo-url> && cd VivaAI
cp .env.example .env
cp frontend/.env.example frontend/.env.local

cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m app.scripts.seed
.venv/bin/python -m app.scripts.seed_demo
.venv/bin/python -m uvicorn app.main:app --port 8000

# new terminal
cd frontend && npm install && npm run dev
```

**Check it is the right backend:** open http://localhost:8000/ready. With real models it must show
`"stt_model_loaded": true`. An "Internal Server Error" there usually means the backend was started with the
wrong Python.

Open http://localhost:3000 and sign in:

| Role | Email | Password |
|---|---|---|
| Teacher | `teacher@vivaiq.edu` | `teacher123` |
| Student | `student@vivaiq.edu` | `student123` |
| Admin | `admin@vivaiq.edu` | `admin123` |

The demo profile uses **mock** models: questions are scripted and transcripts are canned. To run real
vivas, install `requirements-ml.txt` (`.\.venv\Scripts\python -m pip install -r requirements-ml.txt`), run Ollama, and set `DEMO_MODE=false`, `LLM_PROVIDER=ollama`,
`STT_PROVIDER=whisper` (details in the [runbook](docs/runbook.md#2-configuration)).

> The root `.env` overrides `backend/.env` if both exist.

Docker: `docker compose up` (add `--profile gpu` for the CUDA backend).

## Hardware

Designed for a 4 GB GPU (e.g. GTX 1650): Whisper `base.en`/`distil-small.en` (< 1 GB) plus a 2–3B Ollama
model (≈ 2 GB), or a cloud LLM with no VRAM use. All model sizes are environment variables.

## Development

```bash
cd backend && .venv/bin/python -m pytest && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy app
# Windows: .\.venv\Scripts\python -m pytest   (same pattern for ruff and mypy)
cd frontend && npx tsc --noEmit && npx eslint . --max-warnings 0 && npm run build
```

CI (GitHub Actions) runs these plus coverage gates and dependency audits; `pre-commit install` runs them locally.

## Documentation

| Doc | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Components, viva turn pipeline, code layout, hardware sizing |
| [API reference](docs/api-reference.md) | REST endpoints, roles and access rules (live docs at `/api/v1/docs`) |
| [WebSocket protocol](docs/websocket-protocol.md) | Real-time viva events, error codes, reconnect |
| [Authenticity methodology](docs/authenticity-methodology.md) | Signals, scoring, calibration status, **known limitations** |
| [Privacy & retention](docs/privacy-and-retention.md) | What is stored, who can see it, what leaves the server, deletion |
| [Security](docs/security.md) | Controls and known gaps |
| [Runbook & demo script](docs/runbook.md) | Setup, troubleshooting, 10-minute stakeholder demo |
| [Roadmap](docs/ROADMAP.md) | Deferred and not-yet-built items |

## License

MIT
