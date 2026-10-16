"use client";

import React, { useEffect, useRef, useState } from "react";
import { Mic, ShieldCheck, Check, AlertCircle, Volume2 } from "lucide-react";
import Button from "@/components/ui/Button";

interface MicCheckModalProps {
  isOpen: boolean;
  onConsentAndProceed: () => void;
  onCancel: () => void;
  subjectName: string;
}

export default function MicCheckModal({
  isOpen,
  onConsentAndProceed,
  onCancel,
  subjectName,
}: MicCheckModalProps) {
  const [micGranted, setMicGranted] = useState(false);
  const [micVolume, setMicVolume] = useState(0); // 0 to 100
  const [consentChecked, setConsentChecked] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isOpen) {
      stopMic();
      return;
    }

    startMicCheck();

    return () => {
      stopMic();
    };
  }, [isOpen]);

  const startMicCheck = async () => {
    try {
      setErrorMsg(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      setMicGranted(true);

      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      const buffer = new Uint8Array(analyser.frequencyBinCount);

      const updateLevel = () => {
        analyser.getByteFrequencyData(buffer);
        let sum = 0;
        for (let i = 0; i < buffer.length; i++) {
          sum += buffer[i];
        }
        const avg = sum / buffer.length;
        const normalized = Math.min(100, Math.round((avg / 128) * 100));
        setMicVolume(normalized);
        animFrameRef.current = requestAnimationFrame(updateLevel);
      };

      updateLevel();
    } catch (err: any) {
      setErrorMsg("Microphone access was denied. Please allow microphone permissions in your browser.");
      setMicGranted(false);
    }
  };

  const stopMic = () => {
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    setMicVolume(0);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-[var(--bg-card)] rounded-3xl p-6 sm:p-8 border border-[var(--border-default)] shadow-2xl space-y-6 text-[var(--text-primary)] transition-colors">
        {/* Header */}
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] flex items-center justify-center text-[var(--accent-primary)]">
            <Mic className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-editorial text-2xl font-normal text-[var(--text-primary)] tracking-tight">
              Microphone & Readiness Check
            </h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Oral viva voce for: <span className="font-semibold text-[var(--text-primary)]">{subjectName}</span>
            </p>
          </div>
        </div>

        {/* Mic Level Meter */}
        <div className="bg-[var(--bg-card-subtle)] rounded-2xl p-4 border border-[var(--border-default)] space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[var(--text-primary)] font-medium flex items-center gap-1.5">
              <Volume2 className="w-4 h-4 text-[var(--accent-primary)]" />
              Microphone Sensitivity Check
            </span>
            <span className={micGranted ? "text-emerald-500 font-semibold" : "text-amber-500 font-semibold"}>
              {micGranted ? "Microphone Detected" : "Awaiting Permission"}
            </span>
          </div>

          {/* Level Bar */}
          <div className="w-full h-3 rounded-full bg-[var(--bg-card)] border border-[var(--border-default)] overflow-hidden relative">
            <div
              className="h-full bg-[var(--accent-primary)] transition-all duration-75 rounded-full"
              style={{ width: `${Math.max(4, micVolume)}%` }}
            />
          </div>
          <p className="text-[11px] text-[var(--text-muted)]">
            Say a few words out loud to test your microphone input level.
          </p>

          {errorMsg && (
            <div className="flex items-start gap-2 text-xs text-[var(--error-text)] bg-[var(--error-bg)] p-2.5 rounded-xl border border-[var(--error-border)]">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Privacy & Recording Consent */}
        <div className="bg-[var(--bg-card-subtle)] rounded-2xl p-4 border border-[var(--border-default)] space-y-3">
          <div className="flex items-center gap-2 text-[var(--text-primary)] font-medium text-xs">
            <ShieldCheck className="w-4 h-4 text-[var(--accent-primary)]" />
            Candidate Privacy & Examination Consent
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Your oral responses are recorded and transcribed strictly for viva grading and advisory authenticity evaluation. Audio access is restricted exclusively to authorized course instructors.
          </p>
          <label className="flex items-center gap-3 cursor-pointer pt-1 group">
            <input
              type="checkbox"
              checked={consentChecked}
              onChange={(e) => setConsentChecked(e.target.checked)}
              className="w-4 h-4 rounded border-[var(--border-default)] text-[var(--accent-primary)] focus:ring-[var(--border-focus)] bg-[var(--bg-card)] cursor-pointer"
            />
            <span className="text-xs font-medium text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
              I consent to voice audio recording during this examination session.
            </span>
          </label>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onCancel}
          >
            Cancel
          </Button>

          <Button
            type="button"
            variant="primary"
            size="md"
            disabled={!micGranted || !consentChecked}
            onClick={onConsentAndProceed}
          >
            <Check className="w-4 h-4" />
            <span>Enter Examination Room</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
