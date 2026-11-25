/**
 * Typed VivaIQ WebSocket Client for Real-time Voice Viva Voce
 */

export type WSClientEventType = "audio_chunk" | "speech_end" | "repeat_question" | "end_session" | "ping";

export type WSServerEventType =
  | "state_change"
  | "question"
  | "tts_audio"
  | "transcript"
  | "feedback"
  | "session_complete"
  | "error"
  | "pong";

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
  probability: number;
}

export type AuthenticityLevel = "low" | "medium" | "high" | "unknown";

export interface AdvisoryAuthenticity {
  likelihood: AuthenticityLevel;
  confidence: number | null;
  reasons: string[] | null;
  is_advisory: true;
  disclaimer: string;
}

export interface QuestionPayload {
  turn_id: string;
  turn_number: number;
  question_text: string;
  topic: string;
  question_type: string;
  audio_b64: string | null;
  /** MIME type of audio_b64 (e.g. audio/mpeg from EdgeTTS, audio/wav from Piper). */
  audio_mime: string | null;
  is_repeat?: boolean;
}

export interface FeedbackPayload {
  turn_id: string;
  score_0_10: number | null;
  /** False for the warm-up, which only captures the speaking baseline. */
  counts_toward_score: boolean;
  feedback: string;
  rubric: {
    correctness: number;
    completeness: number;
    clarity: number;
    depth: number;
    missing_points: string[];
    incorrect_claims: string[];
  };
  authenticity: AdvisoryAuthenticity;
}

export interface SessionCompletePayload {
  session_id: string;
  student_id: string;
  subject_id: string;
  status: string;
  total_score: number | null;
  turns_count: number;
  authenticity: AdvisoryAuthenticity;
  turn_summaries: Array<{
    turn_number: number;
    question_text: string;
    question_type: string;
    student_transcript: string | null;
    score_0_10: number | null;
    feedback: string | null;
    authenticity_likelihood: AuthenticityLevel;
  }>;
}

export interface WSEventHandlers {
  onStateChange?: (state: string, turnNumber: number) => void;
  onQuestion?: (question: QuestionPayload) => void;
  onTTSAudio?: (audioB64: string, isLast: boolean) => void;
  onTranscript?: (text: string, words: WordTimestamp[]) => void;
  onFeedback?: (feedback: FeedbackPayload) => void;
  onSessionComplete?: (summary: SessionCompletePayload) => void;
  onError?: (error: { code: string; message: string }) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export class VivaWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private baseUrl: string;
  private getTicket?: () => Promise<string>;
  private handlers: WSEventHandlers = {};
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private isExplicitlyClosed = false;

  /**
   * @param ticket Single-use ticket from `api.getWsTicket` (the only accepted WebSocket auth).
   * @param options.getTicket Fetches a fresh single-use ticket. Tickets are consumed on
   *   connect, so reconnecting after a network drop needs a new one.
   */
  constructor(
    sessionId: string,
    ticket: string,
    handlers: WSEventHandlers = {},
    options: { getTicket?: () => Promise<string> } = {}
  ) {
    const wsBase = import.meta.env.VITE_WS_URL || "ws://localhost:8000/api/v1/ws";
    this.baseUrl = `${wsBase}/sessions/${sessionId}`;
    this.url = `${this.baseUrl}?ticket=${encodeURIComponent(ticket)}`;
    this.getTicket = options.getTicket;
    this.handlers = handlers;
  }

  private async reconnect() {
    if (this.getTicket) {
      try {
        this.url = `${this.baseUrl}?ticket=${encodeURIComponent(await this.getTicket())}`;
      } catch (err) {
        this.handlers.onError?.({
          code: "RECONNECT_FAILED",
          message: err instanceof Error ? err.message : "Could not re-authenticate the session.",
        });
        return;
      }
    }
    if (!this.isExplicitlyClosed) this.connect();
  }

  connect() {
    this.isExplicitlyClosed = false;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        this.handlers.onOpen?.();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const type: WSServerEventType = data.type;
          const payload = data.payload || {};

          switch (type) {
            case "state_change":
              this.handlers.onStateChange?.(payload.state, payload.turn_number);
              break;
            case "question":
              this.handlers.onQuestion?.(payload);
              break;
            case "tts_audio":
              this.handlers.onTTSAudio?.(payload.audio_b64, payload.is_last);
              break;
            case "transcript":
              this.handlers.onTranscript?.(payload.text, payload.words || []);
              break;
            case "feedback":
              this.handlers.onFeedback?.(payload);
              break;
            case "session_complete":
              this.handlers.onSessionComplete?.(payload);
              break;
            case "error":
              this.handlers.onError?.(payload);
              break;
            case "pong":
              break;
          }
        } catch (e) {
          console.error("Failed to parse incoming WebSocket message:", e);
        }
      };

      this.ws.onclose = () => {
        this.stopHeartbeat();
        this.handlers.onClose?.();

        // Attempt reconnection if not deliberate close
        if (!this.isExplicitlyClosed && this.reconnectAttempts < this.maxReconnectAttempts) {
          const timeout = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
          this.reconnectAttempts++;
          setTimeout(() => void this.reconnect(), timeout);
        }
      };

      this.ws.onerror = (err) => {
        console.error("WebSocket connection error:", err);
      };
    } catch (err) {
      console.error("Could not initialize WebSocket:", err);
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: "ping", payload: { timestamp: Date.now() } }));
      }
    }, 20000);
  }

  private stopHeartbeat() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  sendAudioChunk(turnId: string, chunkIndex: number, audioB64: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "audio_chunk",
          payload: { turn_id: turnId, chunk_index: chunkIndex, audio_b64: audioB64 },
        })
      );
    }
  }

  sendSpeechEnd(turnId: string, durationMs?: number) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "speech_end",
          payload: { turn_id: turnId, duration_ms: durationMs },
        })
      );
    }
  }

  sendRepeatQuestion(turnId: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "repeat_question",
          payload: { turn_id: turnId },
        })
      );
    }
  }

  sendReady() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "ready",
          payload: {},
        })
      );
    }
  }

  sendEndSession() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: "end_session",
          payload: {},
        })
      );
    }
  }

  disconnect() {
    this.isExplicitlyClosed = true;
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
