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

export interface WSEventHandlers {
  onStateChange?: (state: string, turnNumber: number) => void;
  onQuestion?: (question: any) => void;
  onTTSAudio?: (audioB64: string, isLast: boolean) => void;
  onTranscript?: (text: string, words: WordTimestamp[]) => void;
  onFeedback?: (feedback: any) => void;
  onSessionComplete?: (summary: any) => void;
  onError?: (error: { code: string; message: string }) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export class VivaWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private token: string;
  private handlers: WSEventHandlers = {};
  private pingInterval: any = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private isExplicitlyClosed = false;

  constructor(sessionId: string, authSecret: string, handlers: WSEventHandlers = {}, options: { isTicket?: boolean } = {}) {
    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/ws";
    const authQuery = options.isTicket || authSecret.startsWith("wst_")
      ? `ticket=${authSecret}`
      : `token=${authSecret}`;
    this.url = `${wsBase}/sessions/${sessionId}?${authQuery}`;
    this.token = authSecret;
    this.handlers = handlers;
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

      this.ws.onclose = (event) => {
        this.stopHeartbeat();
        this.handlers.onClose?.();

        // Attempt reconnection if not deliberate close
        if (!this.isExplicitlyClosed && this.reconnectAttempts < this.maxReconnectAttempts) {
          const timeout = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
          this.reconnectAttempts++;
          setTimeout(() => this.connect(), timeout);
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
