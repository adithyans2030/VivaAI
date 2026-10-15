# VivaIQ Real-Time WebSocket Protocol Specification

## Endpoint: `/api/v1/ws/sessions/{session_id}`

The VivaIQ viva examination session uses a full-duplex WebSocket connection to handle real-time audio chunk transmission, speech activity transitions, questions, and transcription events.

---

## 1. Authentication & Session Establishment
- **Handshake URL**: `ws://<host>:<port>/api/v1/ws/sessions/{session_id}?token=<jwt_access_token>`
- **Token Verification**: Validated during the WebSocket upgrade handshake. If the token is invalid or expired, the server terminates with close code `4401` (Unauthorized).
- **Consent Pre-condition**: The session must have `recording_consent: true`. If not provided, the server terminates with close code `4403` (Consent Required).
- **Session Resume**: If a connection drops, reconnecting with the same `session_id` restores the current turn state without losing previous answers or evaluations.

---

## 2. Protocol Messages (Client to Server)

All client-to-server messages are JSON objects containing `type` and `payload`. Audio chunks can also be sent as binary blobs or base64 JSON chunks.

### `audio_chunk`
Streams candidate microphone audio slices (PCM or WebM) while speaking:
```json
{
  "type": "audio_chunk",
  "payload": {
    "turn_id": "turn-uuid-1",
    "chunk_index": 0,
    "audio_b64": "<base64-encoded-audio>"
  }
}
```

### `speech_end`
Emitted by client-side Voice Activity Detection (VAD) or when candidate finishes answering:
```json
{
  "type": "speech_end",
  "payload": {
    "turn_id": "turn-uuid-1",
    "duration_ms": 5420
  }
}
```

### `repeat_question`
Student requests the examiner to repeat the current question:
```json
{
  "type": "repeat_question",
  "payload": {
    "turn_id": "turn-uuid-1"
  }
}
```

### `ping`
Heartbeat keepalive sent every 15-30 seconds:
```json
{
  "type": "ping",
  "payload": {
    "timestamp": 1729000000
  }
}
```

---

## 3. Protocol Messages (Server to Client)

### `state_change`
Signals changes in examiner activity (`examiner_speaking`, `listening`, `processing`, `completed`):
```json
{
  "type": "state_change",
  "payload": {
    "state": "examiner_speaking",
    "turn_number": 1
  }
}
```

### `question`
Broadcasts the synthesized oral viva question:
```json
{
  "type": "question",
  "payload": {
    "turn_id": "turn-uuid-1",
    "turn_number": 1,
    "topic": "Process Synchronization",
    "question_type": "conceptual",
    "question_text": "What is the critical section problem and what three conditions must any valid solution satisfy?",
    "prompt_version": "v1.0"
  }
}
```

### `tts_audio`
Streams synthesized voice audio chunks (PCM / WAV bytes encoded in base64) to be played:
```json
{
  "type": "tts_audio",
  "payload": {
    "turn_id": "turn-uuid-1",
    "chunk_index": 0,
    "audio_b64": "<base64-audio>",
    "is_last": false
  }
}
```

### `transcript`
Returned upon Whisper STT completion with word-level timestamps:
```json
{
  "type": "transcript",
  "payload": {
    "turn_id": "turn-uuid-1",
    "text": "The critical section problem requires mutual exclusion, progress, and bounded waiting.",
    "words": [
      { "word": "The", "start": 0.12, "end": 0.28, "probability": 0.98 },
      { "word": "critical", "start": 0.30, "end": 0.65, "probability": 0.97 },
      { "word": "section", "start": 0.66, "end": 1.02, "probability": 0.99 }
    ]
  }
}
```

### `feedback`
Immediate rubric assessment and examiner remarks after grading:
```json
{
  "type": "feedback",
  "payload": {
    "turn_id": "turn-uuid-1",
    "score_0_10": 9.0,
    "feedback": "Excellent definition capturing mutual exclusion, progress, and bounded waiting clearly.",
    "rubric": {
      "correctness": 9.5,
      "completeness": 9.0,
      "clarity": 9.0,
      "depth": 8.5
    }
  }
}
```

### `session_complete`
Emitted when the planned number of questions (e.g. 6-10) is fulfilled:
```json
{
  "type": "session_complete",
  "payload": {
    "session_id": "sess-uuid-1",
    "total_score": 8.6,
    "overall_authenticity": "low",
    "turns_count": 8
  }
}
```

### `pong`
Keepalive response:
```json
{
  "type": "pong",
  "payload": {
    "timestamp": 1729000000
  }
}
```
