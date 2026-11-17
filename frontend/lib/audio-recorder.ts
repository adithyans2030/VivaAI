/**
 * Browser Audio Recorder with Real-time Stream Chunking & Silence Detection (VAD)
 */

/** Safari < 14.1 only exposes the prefixed constructor. */
export type WebkitWindow = Window & { webkitAudioContext?: typeof AudioContext };

export interface AudioRecorderOptions {
  onAudioChunk: (chunkB64: string, chunkIndex: number) => void;
  onVolumeChange?: (volume: number) => void;
  onSpeechEnd?: (durationMs: number) => void;
  /** Pause length that ends the answer. Long enough for a student to stop and think. */
  silenceThresholdMs?: number;
  /** Speech needed before a pause may end the answer, so a cough or click cannot submit it. */
  minSpeechMs?: number;
}

/** Normalised level above which a frame counts as speech. */
const SPEECH_LEVEL = 0.08;

export class AudioStreamRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private stream: MediaStream | null = null;
  private chunkIndex = 0;
  private startTime = 0;
  private animFrame: number | null = null;
  private silenceTimer: ReturnType<typeof setTimeout> | null = null;
  private isSpeaking = false;
  private speechMs = 0;
  private lastFrameAt = 0;
  private stopPromise: Promise<number> | null = null;
  private pendingChunks: Promise<void> = Promise.resolve();
  private options: AudioRecorderOptions;

  constructor(options: AudioRecorderOptions) {
    this.options = {
      silenceThresholdMs: 3500,
      minSpeechMs: 800,
      ...options,
    };
  }

  async start() {
    this.chunkIndex = 0;
    this.startTime = Date.now();
    this.isSpeaking = false;
    this.speechMs = 0;
    this.lastFrameAt = 0;
    this.stopPromise = null;
    this.pendingChunks = Promise.resolve();

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    // stop() may have been called while the permission prompt / device open was pending.
    if (this.stopPromise) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
      return;
    }

    // Audio Analysis for volume meter & silence detection
    const AudioCtx = window.AudioContext || (window as WebkitWindow).webkitAudioContext;
    this.audioContext = new AudioCtx();
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;

    const source = this.audioContext.createMediaStreamSource(this.stream);
    source.connect(this.analyser);

    const buffer = new Uint8Array(this.analyser.frequencyBinCount);

    const checkVolume = () => {
      if (!this.analyser) return;
      this.analyser.getByteFrequencyData(buffer);
      let sum = 0;
      for (let i = 0; i < buffer.length; i++) {
        sum += buffer[i];
      }
      const avg = sum / buffer.length;
      const normalized = Math.min(1.0, avg / 128.0);
      this.options.onVolumeChange?.(normalized);

      // Voice Activity Detection (VAD): only a real stretch of speech followed by a long pause
      // ends the answer automatically; the student can always press Submit themselves.
      const now = performance.now();
      const frameMs = this.lastFrameAt ? Math.min(now - this.lastFrameAt, 100) : 0;
      this.lastFrameAt = now;
      if (normalized > SPEECH_LEVEL) {
        this.speechMs += frameMs;
        if (this.speechMs >= (this.options.minSpeechMs ?? 0)) this.isSpeaking = true;
        if (this.silenceTimer) {
          clearTimeout(this.silenceTimer);
          this.silenceTimer = null;
        }
      } else if (this.isSpeaking && !this.silenceTimer) {
        // Candidate was speaking and has now paused
        this.silenceTimer = setTimeout(() => {
          if (this.isSpeaking) {
            void this.stop().then((durationMs) => this.options.onSpeechEnd?.(durationMs));
          }
        }, this.options.silenceThresholdMs);
      }

      this.animFrame = requestAnimationFrame(checkVolume);
    };

    checkVolume();

    // MediaRecorder for chunk encoding
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    this.mediaRecorder = new MediaRecorder(this.stream, { mimeType });

    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size === 0) return;
      const index = this.chunkIndex++;
      // Chain conversions so chunks are sent in order and stop() can await the last one.
      this.pendingChunks = this.pendingChunks
        .then(() => e.data.arrayBuffer())
        .then((buf) => this.options.onAudioChunk(this.arrayBufferToBase64(buf), index))
        .catch((err) => console.warn("Dropped audio chunk", index, err));
    };

    // Emit chunk every 350ms
    this.mediaRecorder.start(350);
  }

  /**
   * Stop recording. Resolves with the answer duration once the final chunk has been
   * emitted, so callers can send `speech_end` without racing the last audio_chunk.
   * Safe to call more than once.
   */
  stop(): Promise<number> {
    if (this.stopPromise) return this.stopPromise;

    if (this.animFrame) cancelAnimationFrame(this.animFrame);
    if (this.silenceTimer) clearTimeout(this.silenceTimer);
    this.animFrame = null;
    this.silenceTimer = null;
    const durationMs = Date.now() - this.startTime;
    const recorder = this.mediaRecorder;

    this.stopPromise = new Promise<number>((resolve) => {
      if (!recorder || recorder.state === "inactive") {
        resolve(durationMs);
        return;
      }
      // The final dataavailable fires before onstop; wait for its conversion to be sent.
      recorder.onstop = () => {
        void this.pendingChunks.then(() => resolve(durationMs));
      };
      recorder.stop();
    }).then((d) => {
      this.stream?.getTracks().forEach((t) => t.stop());
      this.stream = null;
      this.audioContext?.close().catch(() => {});
      this.audioContext = null;
      this.analyser = null;
      return d;
    });
    return this.stopPromise;
  }

  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    let binary = "";
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }
}
