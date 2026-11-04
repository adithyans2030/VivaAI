# VivaIQ WebSocket Protocol

**Endpoint:** `GET /api/v1/ws/sessions/{session_id}` (WebSocket upgrade)
**Source of truth:** `backend/app/ws/session_handler.py` (server), `frontend/lib/ws.ts` (client)

Every message in both directions is a JSON object `{"type": string, "payload": object}`.

---

## 1. Connecting

### 1.1 Get a ticket, then connect

1. The student creates a session (`POST /api/v1/sessions`) and records consent
   (`POST /api/v1/sessions/{id}/consent` with `{"recording_consent": true}`).
2. The client requests a ticket: `POST /api/v1/sessions/{id}/ws-ticket` → `{"ticket": "...", "expires_in": 30}`.
3. The client connects to `ws://<host>/api/v1/ws/sessions/{id}?ticket=<ticket>`.

Tickets are **single-use** and expire after **30 seconds**. Because a ticket is consumed on connect,
**every reconnect needs a new ticket**; `VivaWebSocketClient` does this automatically through its
`getTicket` option.

> `?token=<access JWT>` is still accepted as a fallback (the test suite uses it). Browsers should always
> use tickets: URLs end up in proxy and access logs, and a ticket is worthless once used.

### 1.2 Close codes

| Code | Meaning |
|---|---|
| `4401` | Ticket/token invalid, expired or already used |
| `4404` | Session does not exist |
| `4403` | Not this student's session, or recording consent has not been given |
| `1000` | Normal close, idle timeout (60 s without any client message), or replaced by a newer connection for the same session |

Only one connection per session is kept: a new connection closes the previous one.

### 1.3 On connect: `session_state`

Immediately after accepting, the server sends the current state so a reconnecting client can resume:

```json
{
  "type": "session_state",
  "payload": {
    "session_id": "…",
    "status": "in_progress",
    "recording_consent": true,
    "subject": { "id": "…", "name": "Operating Systems & Concurrency" },
    "active_turn": { "turn_id": "…", "turn_number": 3, "question_text": "…", "question_type": "application" }
  }
}
```

The client then sends `ready` to receive the next (or still-unanswered) question.

---

## 2. Client → server

| Type | Payload | Effect |
|---|---|---|
| `ready` (alias `request_question`) | `{}` | Server sends the next question, or `session_complete` when the planned number of questions is reached. Sent on connect and after each `feedback`. |
| `audio_chunk` | `{turn_id, chunk_index, audio_b64}` | Appends base64 audio (browser WebM/Opus from `MediaRecorder`) to the turn's buffer. |
| `speech_end` | `{turn_id, duration_ms?}` | Answer finished: server transcribes, grades and analyses it. Sent only after the recorder has flushed its final chunk. |
| `repeat_question` | `{turn_id}` | Replays the question. **One repeat per turn.** |
| `end_session` | `{}` | Ends the viva early; server finalises the report. |
| `ping` | `{timestamp}` | Heartbeat (client sends every 20 s); server answers `pong`. |

**Backpressure / limits:** the audio buffer for a turn is capped at **9.6 MB**;
beyond that the server replies `AUDIO_BUFFER_OVERFLOW` and drops further chunks for that turn.

---

## 3. Server → client

### `state_change`
`{"state": "examiner_speaking" | "listening" | "processing" | "completed", "turn_number": n}`

The browser drives `examiner_speaking`/`listening` from actual audio playback and the microphone,
and treats the server as authoritative for `processing` and `completed`.

### `question`
```json
{
  "type": "question",
  "payload": {
    "turn_id": "…",
    "turn_number": 2,
    "question_text": "Explain how a counting semaphore differs from a mutex.",
    "topic": "Process Synchronization",
    "question_type": "compare_contrast",
    "audio_b64": "<base64 audio or null>",
    "audio_mime": "audio/mpeg",
    "is_repeat": false
  }
}
```

`audio_b64` is server-side TTS for the whole question (`audio_mime`: `audio/mpeg` from EdgeTTS,
`audio/wav` from Piper). When it is `null` (`TTS_PROVIDER=browser`, or synthesis failed) the browser
speaks the question with the Web Speech API. `is_repeat: true` marks a replay requested by `repeat_question`.

### `transcript`
`{"turn_id", "text", "words": [{"word", "start", "end", "probability"}]}`. Whisper output with word timestamps.

### `feedback`
```json
{
  "type": "feedback",
  "payload": {
    "turn_id": "…",
    "score_0_10": 7.5,
    "feedback": "Correct on mutual exclusion; did not explain bounded waiting.",
    "rubric": {
      "correctness": 8, "completeness": 6, "clarity": 8, "depth": 7,
      "missing_points": ["bounded waiting"], "incorrect_claims": []
    },
    "authenticity": {
      "likelihood": "low",
      "confidence": 0.82,
      "reasons": ["…"],
      "is_advisory": true,
      "disclaimer": "Advisory signal to support teacher judgment, not an automated accusation."
    }
  }
}
```

### `session_complete`
The final report: `session_id`, `student_id`, `subject_id`, `status`, `total_score`, `turns_count`,
`authenticity` (same advisory shape as above) and `turn_summaries[]`
(`turn_number`, `question_text`, `question_type`, `student_transcript`, `score_0_10`, `feedback`, `authenticity_likelihood`).

### `error`
`{"code": string, "message": string}`. The connection stays open unless stated otherwise.

| Code | Cause |
|---|---|
| `INVALID_AUDIO_ENCODING` | `audio_b64` is not valid base64 |
| `AUDIO_BUFFER_OVERFLOW` | Turn audio exceeded 9.6 MB |
| `INVALID_TURN` | Missing `turn_id`, or the turn does not belong to this session |
| `EMPTY_AUDIO` | `speech_end` arrived with no audio buffered |
| `STT_FAILED` | Transcription failed (details are in the server log) |
| `REPEAT_LIMIT_EXCEEDED` | Second repeat requested for the same turn |
| `SESSION_NOT_FOUND` | Session deleted while connected |
| `WS_ERROR` | Unexpected server error; message is generic, details are logged server-side. Reconnect to resume. |

### `pong`
`{"timestamp": <unix seconds>}`

---

## 4. Not implemented (see ROADMAP)

- **`partial_transcript`**: live captions currently come from the browser's own speech recognition
  (where available); the server sends only the final `transcript`.
- **`tts_audio` streaming**: question audio is sent whole inside `question`, not as streamed
  sentence chunks, so first-audio latency includes full synthesis.
