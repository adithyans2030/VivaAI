/**
 * Browser Audio Recorder with Real-time Stream Chunking & Silence Detection (VAD)
 */

export interface AudioRecorderOptions {
  onAudioChunk: (chunkB64: string, chunkIndex: number) => void;
  onVolumeChange?: (volume: number) => void;
  onSpeechEnd?: (durationMs: number) => void;
  silenceThresholdMs?: number;
}

export class AudioStreamRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private stream: MediaStream | null = null;
  private chunkIndex = 0;
  private startTime = 0;
  private animFrame: number | null = null;
  private silenceTimer: any = null;
  private isSpeaking = false;
  private options: AudioRecorderOptions;

  constructor(options: AudioRecorderOptions) {
    this.options = {
      silenceThresholdMs: 1800,
      ...options,
    };
  }

  async start() {
    this.chunkIndex = 0;
    this.startTime = Date.now();
    this.isSpeaking = false;

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    // Audio Analysis for volume meter & silence detection
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
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

      // Voice Activity Detection (VAD) logic
      if (normalized > 0.08) {
        this.isSpeaking = true;
        if (this.silenceTimer) {
          clearTimeout(this.silenceTimer);
          this.silenceTimer = null;
        }
      } else if (this.isSpeaking && !this.silenceTimer) {
        // Candidate was speaking and has now paused
        this.silenceTimer = setTimeout(() => {
          if (this.isSpeaking) {
            const durationMs = Date.now() - this.startTime;
            this.options.onSpeechEnd?.(durationMs);
            this.stop();
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

    this.mediaRecorder.ondataavailable = async (e) => {
      if (e.data.size > 0) {
        const arrayBuffer = await e.data.arrayBuffer();
        const base64 = this.arrayBufferToBase64(arrayBuffer);
        this.options.onAudioChunk(base64, this.chunkIndex++);
      }
    };

    // Emit chunk every 350ms
    this.mediaRecorder.start(350);
  }

  stop(): number {
    if (this.animFrame) cancelAnimationFrame(this.animFrame);
    if (this.silenceTimer) clearTimeout(this.silenceTimer);

    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      this.mediaRecorder.stop();
    }

    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }

    if (this.audioContext) {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }

    return Date.now() - this.startTime;
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
