# VivaIQ — AI Voice Viva Examiner

VivaIQ is a production-grade web application in which an AI examiner conducts oral (*viva voce*) examinations with students by voice, grades answers based on retrieved subject matter, and provides an advisory, explainable authenticity assessment (detecting if a student is reading from notes rather than answering spontaneously in their own words).

---

## Key Features

- **Real-time Voice Viva**: Interactive voice examination with natural pacing and speech activity detection (Silero VAD).
- **RAG-Grounded Questioning**: Topic extraction and chunk retrieval from uploaded PDFs, DOCX, TXT, and Markdown files.
- **Adaptive Probing**: Examiners pose conceptual, application, and comparative questions, with dynamic follow-ups based on student performance.
- **Subject-Grounded Grading**: Multi-dimensional rubrics (correctness, completeness, clarity, depth) with actionable feedback.
- **Explainable Authenticity Analysis**: Advisory detection of reading vs. spontaneous speaking across 6 distinct signals (verbatim overlap, disfluency rate, pauses, prosody, response latency, and probe resilience).
- **Teacher Dashboard**: Comprehensive reports, audio review with timestamped transcripts, class analytics, grade overrides with audit logs, and CSV export.
- **Provider-Agnostic Engine**: Seamlessly switch between Ollama (local demo), Gemini, or Grok via environment variables.

---

## Hardware Target: NVIDIA GTX 1650 (4GB VRAM)

To deliver low-latency voice interactions on consumer hardware (4GB VRAM):
- **STT**: `faster-whisper` (`distil-small.en` or `base.en`) with int8/float16 quantization (<800MB VRAM).
- **LLM**: Cloud-backed via `GeminiProvider` (zero VRAM footprint) or local `OllamaProvider` (`qwen2.5:3b` / `llama3.2:3b` in ~2GB VRAM).
- **RAG Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` or `bge-small-en-v1.5` (<150MB VRAM).
- **TTS**: High-efficiency Piper or client-side Web Speech API fallback.

---

## Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) Docker & Docker Compose
- (Optional) NVIDIA GPU with CUDA drivers

### 1. Clone & Configure Environment
```bash
git clone <repo-url>
cd VivaAI
cp .env.example .env
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

Run tests to verify the installation:
```bash
pytest -v
```

Start the FastAPI backend server:
```bash
uvicorn app.main:app --reload --port 8000
```
API Documentation will be accessible at: `http://localhost:8000/api/v1/docs`

### 3. Docker Deployment
```bash
docker compose up -d backend
# With local Ollama GPU acceleration:
docker compose --profile gpu up -d
```

---

## Architecture

```
Browser (Next.js)  <-- WebSocket (audio/events) + REST -->  FastAPI
                                                              |
        +-----------+-----------+-----------+-----------+-----+------+
        |           |           |           |           |            |
       STT        RAG        LLM Gateway    TTS     Authenticity   DB/Storage
   (Whisper)   (Chroma)   (Ollama|Gemini|  (Piper)   Analyzer     (SQL + files)
                              Grok)
```

---

## License
MIT
