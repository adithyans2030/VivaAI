# Privacy & Data Retention

This describes what VivaIQ stores about students, who can see it, how long it is kept, and where it can leave
the server. It reflects the current code; if you change providers or deployment, re-check section 4.

> This is a technical description, not legal advice. Your institution should review it against its own
> obligations (e.g. GDPR, India's DPDP Act 2023, FERPA) before using VivaIQ with real students.

## 1. What is collected

| Data | When | Where it is stored |
|---|---|---|
| Account: email, full name, bcrypt password hash, role | Registration / admin creation | Database (`users`) |
| Recording consent flag | Before every viva (mandatory checkbox) | Database (`viva_sessions.recording_consent`) |
| **Voice recordings** of each answer | During the viva, only after consent | Disk: `AUDIO_STORAGE_PATH/<session_id>/` |
| Transcripts with word timestamps | After each answer | Database (`turns`) |
| Scores, rubric breakdown, feedback | After each answer | Database (`turns`, `viva_sessions`) |
| Authenticity features and reasons (pause, pitch, disfluency, overlap metrics) | After each answer | Database (`turns.speech_features`, reasons) |
| Teacher notes, overrides with reasons | When a teacher acts | Database (`score_overrides`, `audit_logs`) |
| Security records: revoked token ids, WebSocket tickets, login/registration attempt keys (IP + email) | On refresh/logout, viva connect, login | Database; purged automatically (tickets after 1 h, attempts after 24 h, revocations once the token would have expired) |
| Course documents and their embeddings | Teacher upload | Disk: `DOCUMENT_STORAGE_PATH`, `CHROMA_PERSIST_PATH` |

No video, face or gaze data is collected. Live captions shown to the student come from the browser's
own speech recognition (Chrome/Edge may process this audio on the browser vendor's servers); they are
not stored. The stored transcript is produced by the server's Whisper model.

## 2. Consent

A viva cannot start without consent: the WebSocket refuses audio (close code `4403`) until
`recording_consent` is true, and the student must tick the consent box in the microphone-check dialog.
Consent is stored with the session.

## 3. Who can access what

| Role | Access |
|---|---|
| Student | Their own sessions, reports and recordings only |
| Teacher | Sessions, transcripts, recordings, notes and exports **only for subjects they own** |
| Admin | Everything; creates teacher/admin accounts |

The same rule is enforced on every session endpoint and on audio downloads (see
[api-reference.md](api-reference.md#session-access-rule)). Score and flag overrides are recorded in the
audit log with the teacher, the before/after values and a mandatory reason.

The authenticity assessment is **advisory only**. It never changes a score automatically and is
labelled as advisory in the UI, API payloads and exports. See [authenticity-methodology.md](authenticity-methodology.md).

## 4. Data leaving the server

This depends entirely on configuration:

| Setting | What is sent off-machine |
|---|---|
| `LLM_PROVIDER=ollama` (default for demo) | Nothing; the model runs locally |
| `LLM_PROVIDER=gemini` | Student **transcripts** and retrieved **course material** go to Google's Gemini API |
| `LLM_PROVIDER=grok` | The same data goes to xAI's API |
| `STT_PROVIDER=whisper` | Nothing; transcription is local. Voice recordings never leave the server. |
| `TTS_PROVIDER=edge` | **Question text** (not student data) goes to Microsoft's Edge TTS service |
| `TTS_PROVIDER=piper` or `browser` | Nothing |

Before enabling a cloud LLM for real students, check the provider's data-retention and training terms
and your institution's rules on sending student work to third parties.

## 5. Retention

| Data | Retention |
|---|---|
| Voice recordings | Deleted automatically for **every session older than `AUDIO_RETENTION_DAYS`** (default **30**), including sessions abandoned mid-viva. The sweep runs at server start and then every 24 hours. |
| Transcripts, scores, reports, audit log | Kept until the student's account is deleted (no automatic expiry yet; see ROADMAP) |
| Course documents | Until a teacher deletes them |
| Logs | Application logs omit passwords and tokens. Gemini API keys are sent in a header, not the URL, so they do not appear in request logs. |

## 6. Student rights: export and deletion

- **Export:** `GET /api/v1/auth/me/export-data` returns the student's profile and every session with
  questions, transcripts, scores and feedback as JSON.
- **Deletion:** `DELETE /api/v1/auth/me/delete-account-data` permanently deletes the account, all sessions
  and turns, and all recordings on disk. This cannot be undone.

These are API endpoints; there is not yet a button for them in the student UI (see ROADMAP).

## 7. Security measures

Summarised in [security.md](security.md): bcrypt password hashing, short-lived JWTs with refresh rotation,
single-use WebSocket tickets, role and ownership checks, upload type validation, rate limiting on
login/registration, explicit-origin CORS, and secrets only via environment variables.
