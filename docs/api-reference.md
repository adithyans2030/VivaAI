# VivaIQ REST API Reference

Base URL: `http://<host>:8000/api/v1`. The interactive OpenAPI docs are at **`/api/v1/docs`** (Swagger) and
`/api/v1/redoc`; they are generated from the code and always current, with full request and response
schemas. This page summarises the endpoints, who may call them, and the rules that are not visible in the schema.

The real-time viva channel is documented separately in [websocket-protocol.md](websocket-protocol.md).

## Conventions

- **Auth:** `Authorization: Bearer <access_token>`. Access tokens last 30 min (`ACCESS_TOKEN_EXPIRE_MINUTES`).
  The frontend refreshes automatically on a 401 and retries once.
- **Errors:** `{"detail": "message"}`. Validation errors (422) return `detail` as a list of `{loc, msg}`.
- **Request IDs:** every response carries `X-Request-ID` (echoed if you send one) and `X-Process-Time-Ms`.
- **Roles:** `student`, `teacher`, `admin`. Admins pass every role check.

### Session access rule

Every endpoint that reads or changes a viva session (details, state, report, notes, override, CSV, audio, WebSocket ticket)
applies the same rule:

| Role | May access |
|---|---|
| Student | Only their own sessions |
| Teacher | Only sessions in subjects they own (`subject.teacher_id`) |
| Admin | All sessions |

Anything else returns **403**. `GET /sessions` applies the same rule as a filter.

## System

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | public | Liveness: `{"status": "healthy"}` (not under `/api/v1`) |
| GET | `/ready` | public | Readiness: reports STT/LLM/TTS provider status (not under `/api/v1`) |

## Auth (`/auth`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/register` | public | Creates a **student** account; any `role` in the body is ignored. Password ≥ 8 chars. Rate limit: 10/min per IP. |
| POST | `/auth/login` | public | Form-encoded `username` (email) + `password` (OAuth2 password flow). Returns `access_token`, `refresh_token`, `expires_in`. Rate limit: 10/min per IP+email. |
| POST | `/auth/refresh` | public | `{"refresh_token"}` → new access **and** refresh token. The old refresh token is revoked (rotation, persisted in the DB); reusing it returns 401. |
| POST | `/auth/logout` | any user | Optional `{"refresh_token"}` to revoke. |
| GET | `/auth/me` | any user | Current profile. |
| GET | `/auth/me/export-data` | any user | Data export: profile plus every session with turns, transcripts, scores and feedback. |
| DELETE | `/auth/me/delete-account-data` | any user | Permanently deletes the caller's account, sessions and audio. |
| POST | `/auth/admin/users` | admin | Create `teacher` or `admin` accounts (the only way to create them). |

## Subjects & documents

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/subjects` | any user | All subjects. |
| POST | `/subjects` | teacher | `{name, code, description}`; the caller becomes the owner. |
| GET | `/subjects/{id}` | any user | Includes documents. |
| PUT | `/subjects/{id}` | teacher | Partial update. |
| DELETE | `/subjects/{id}` | teacher | Deletes the subject and its documents. |
| GET | `/subjects/{id}/documents` | any user | |
| POST | `/subjects/{id}/documents` | teacher | Multipart `file`. PDF, DOCX, TXT or MD; **≤ 25 MB**; content is checked against the extension's magic bytes (a renamed `.exe` is rejected). Ingestion (parse → chunk → embed → Chroma) runs in the background. |
| GET | `/documents/{id}/status` | any user | `ingestion_status`: `pending` / `processing` / `completed` / `failed`, `chunk_count`, `error_message`. |
| DELETE | `/documents/{id}` | teacher | Removes the file and its vectors. |

## Sessions (`/sessions`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/sessions` | any user | `{"subject_id"}`; creates a session for the caller with `recording_consent: false`. |
| POST | `/sessions/{id}/consent` | owner student / admin | `{"recording_consent": true}`. Required before the WebSocket will accept audio. |
| GET | `/sessions` | any user | Filters: `subject_id`, `student_id`, `status_filter`, `flag_level`. Rows include `student_name`, `subject_name`, `subject_code`. |
| GET | `/sessions/{id}` | session access rule | Full record including `turns[]` (question, transcript, word timestamps, rubric, feedback, authenticity reasons, source references, prompt version). |
| GET | `/sessions/{id}/state` | session access rule | Lightweight resume state (same as the WebSocket `session_state`). |
| POST | `/sessions/{id}/ws-ticket` | session access rule | `{"ticket", "expires_in": 30}`; single-use. 400 if the session is completed or cancelled. |
| GET | `/sessions/{id}/turns/{turn_id}/audio` | session access rule | The student's recorded answer (WAV). Alias: `GET /audio/{session_id}/{turn_id}`. |

## Reports (`/reports`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/reports/sessions/{id}` | session access rule | Report with turns, analytics and the **advisory** authenticity summary. |
| POST | `/reports/sessions/{id}/notes` | teacher + access rule | `{"teacher_notes"}` (≤ 5000 chars). |
| POST | `/reports/sessions/{id}/override` | teacher + access rule | `{turn_id?, new_score (0–10), new_authenticity?, reason (≥ 5 chars)}`. Writes a `ScoreOverride` row and an `AuditLog` entry with before/after values. With `turn_id`, the session total is recomputed as the mean of turn scores. |
| GET | `/reports/sessions/{id}/export/csv` | teacher + access rule | CSV of questions, transcripts, scores and authenticity flags; authenticity columns are labelled **(Advisory)** and an advisory note ends the file. |
| GET | `/reports/sessions/{id}/export/pdf` | teacher + access rule | Printable report: session details, advisory authenticity panel with reasons, teacher notes, and every question with rubric, answer, feedback and sources. |
