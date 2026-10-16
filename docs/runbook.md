# VivaIQ Operator Runbook & Stakeholder Demo Guide

This runbook describes how to launch, configure, test, and demonstrate **VivaIQ**—an AI Voice Viva Voce Examiner with RAG-grounded oral questioning, multi-dimensional rubric grading, and explainable, advisory authenticity assessment.

---

## 1. System Overview & Architecture

- **Backend**: FastAPI with async SQLAlchemy, SQLite (`vivaiq.db`), and WebSockets.
- **Frontend**: Next.js App Router (React 19), Tailwind CSS, Lucide icons, Canvas Audio Visualizer, and Web Speech API.
- **LLM Gateway**: Local **Ollama** (`gemma2:2b` or `llama3.1:latest`), with pluggable support for Google Gemini and xAI Grok.
- **Speech-to-Text (STT)**: `faster-whisper` (`base.en` on CUDA or CPU) with word-level timestamps.
- **Text-to-Speech (TTS)**: Web Speech Synthesis API (browser native) and backend audio streaming.
- **Knowledge Engine (RAG)**: ChromaDB vector store + TF-IDF fallback for grounded source citation.
- **Authenticity Assessment**: Advisory 6-signal analysis engine (Verbatim N-grams, Disfluency Rate, Pause Distribution, Prosodic Variability, Onset Latency, Dynamic Probe Delta).

---

## 2. Prerequisites

| Component | Minimum Version | Note |
| :--- | :--- | :--- |
| **Operating System** | Windows 10/11, macOS, or Linux | Tested on Windows with NVIDIA GTX 1650 |
| **Python** | 3.12+ | Installed in `backend/.venv` |
| **Node.js** | 20+ (Node 24 recommended) | In `frontend` |
| **Ollama** | 0.4.0+ | Must be running on `http://localhost:11434` |

### Installing the Recommended Local Model in Ollama:
```powershell
# Optimized for 4GB VRAM (GTX 1650):
ollama pull gemma2:2b

# Alternatively for 8GB+ VRAM:
ollama pull llama3.1:latest
```

---

## 3. Environment Configuration

### Backend (`backend/.env`):
```ini
PROJECT_NAME="VivaIQ"
API_V1_STR="/api/v1"
SECRET_KEY="temporary-secret-key-change-in-production"
ENVIRONMENT="development"
DEBUG=True

# LLM Gateway
LLM_PROVIDER="ollama"
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="gemma2:2b"

# STT Configuration
STT_PROVIDER="whisper"
WHISPER_MODEL="base.en"
WHISPER_DEVICE="cuda"
WHISPER_COMPUTE_TYPE="float16"

# TTS Configuration
TTS_PROVIDER="browser"
```

---

## 4. One-Command Demo Database Seeding

To seed the database with course materials, teachers, students, and pre-recorded viva sessions (both authentic and flagged note-reading):

```powershell
cd c:\Users\adith\OneDrive\Desktop\VivaAI\backend
.\.venv\Scripts\python -m app.scripts.seed_demo
```

### Pre-Seeded Credentials:
- **Teacher Account**: `teacher@vivaiq.edu` / `TeacherPass123!`
- **Authentic Student (Alex Lovelace)**: `alex@student.edu` / `StudentPass123!`
- **Scripted Student (Robert Smith)**: `robert@student.edu` / `StudentPass123!`
- **Course**: `CS301: Operating Systems & Concurrency`

---

## 5. Starting the Application

### Start the Backend (Port 8000):
```powershell
cd c:\Users\adith\OneDrive\Desktop\VivaAI\backend
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- Interactive Swagger Docs: `http://127.0.0.1:8000/api/v1/docs`
- Health Check: `http://127.0.0.1:8000/health`
- Readiness Probe: `http://127.0.0.1:8000/ready`

### Start the Frontend (Port 3000):
```powershell
cd c:\Users\adith\OneDrive\Desktop\VivaAI\frontend
npm run dev
```
Open **`http://localhost:3000`** in Google Chrome or Microsoft Edge.

---

## 6. Stakeholder Demonstration Script (Step-by-Step)

### Scene 1: The Student Viva Experience
1. Open `http://localhost:3000/student` in your browser.
2. Select the course **CS301: Operating Systems & Concurrency**.
3. Click **"Begin Microphone Check & Consent"**.
   - Speak into your microphone to watch the real-time audio visualizer waveform react.
   - Check the mandatory recording consent checkbox and click **"Proceed to Viva Room"**.
4. The **Animated Audio Orb** initializes in `examiner_speaking` mode, reading out the warmup question:
   > *"Welcome to your oral viva examination. Could you introduce yourself and tell me what area of operating systems you enjoyed studying most?"*
5. Answer naturally into your microphone:
   - Notice the **Live Speech Captions** transcribe your words in real time.
   - Click **"Finish & Submit Answer"**.
6. The examiner transitions to `processing`, computes rubric grading and advisory authenticity, provides constructive feedback, and adaptively formulates the next technical question grounded in the syllabus.

---

### Scene 2: The Teacher Audit & Authenticity Review
1. Open `http://localhost:3000/teacher` in your browser (or log in as `teacher@vivaiq.edu`).
2. Review the **Viva Voce Examination Sessions** table:
   - **Ada / Alex Lovelace**: 8.8 / 10, **Low Risk** Authenticity flag.
   - **Robert Smith**: 6.2 / 10, **High Risk** Authenticity flag.
3. Click on **Robert Smith** to inspect the turn breakdown:
   - **Turn 1 (Coffman Conditions)**:
     - Student scored 9.0 on correctness, but the **Authenticity Diagnostics** flagged:
       - *High 4-gram verbatim overlap with course notes (72%)*.
       - *Unusually low disfluency rate (0.2 fillers/100 words)*.
       - *Mid-clause visual scanning pause pattern*.
   - **Turn 2 (Probe Question)**:
     - When asked to depart from textbook definitions with an everyday analogy, score dropped from 9.0 to 3.5.
4. Listen to the student's recorded voice by clicking the audio playback trigger on each turn.
5. Demonstrate **Human-in-the-Loop Teacher Override**:
   - Click **"Manual Grade Override"**.
   - Adjust the score or flag, input a justification (*"Adjusted score down due to clear textbook recital without spontaneous explanation"*), and click **"Confirm Override"**.
   - Point out that the override is permanently recorded in the **Immutable Audit Log**.
6. Click **"Export CSV"** to download the complete examination audit trail.

---

## 7. Running the Test Suite

To run all 20 automated tests across unit, integration, RAG, and WebSocket pipelines:

```powershell
cd c:\Users\adith\OneDrive\Desktop\VivaAI\backend
.\.venv\Scripts\pytest -v
```

All tests execute in ~5 seconds using fast mock providers for STT and LLM, allowing continuous verification on non-GPU environments.
