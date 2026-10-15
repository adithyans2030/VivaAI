"use client";

import React, { useEffect, useRef, useState } from "react";
import { Mic, ShieldCheck, Check, AlertCircle, Volume2 } from "lucide-react";

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
      setErrorMsg("Microphone access was denied. Please allow microphone permissions to take this viva.");
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-lg glass-panel bg-slate-900/90 rounded-2xl p-6 border border-slate-700/80 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Mic className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Audio & System Readiness</h2>
            <p className="text-xs text-slate-400">Oral examination for: <span className="text-indigo-300 font-semibold">{subjectName}</span></p>
          </div>
        </div>

        {/* Mic Level Meter */}
        <div className="bg-slate-950/60 rounded-xl p-4 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium flex items-center gap-1.5">
              <Volume2 className="w-4 h-4 text-emerald-400" />
              Microphone Sensitivity Check
            </span>
            <span className={micGranted ? "text-emerald-400 font-semibold" : "text-amber-400 font-semibold"}>
              {micGranted ? "Microphone Detected" : "Awaiting Permission"}
            </span>
          </div>

          {/* Level Bar */}
          <div className="w-full h-3 rounded-full bg-slate-800/80 overflow-hidden relative">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-sky-400 transition-all duration-75"
              style={{ width: `${Math.max(4, micVolume)}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">
            Say something out loud to test your microphone input level.
          </p>

          {errorMsg && (
            <div className="flex items-start gap-2 text-xs text-rose-400 bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/20">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Consent Accord */}
        <div className="bg-indigo-950/20 rounded-xl p-4 border border-indigo-800/30 space-y-3">
          <div className="flex items-center gap-2 text-indigo-300 font-medium text-xs">
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
            Candidate Privacy & Examination Consent
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Your oral responses will be recorded and transcribed strictly for viva grading and advisory authenticity evaluation. Audio access is restricted exclusively to authorized course instructors.
          </p>
          <label className="flex items-center gap-3 cursor-pointer pt-1 group">
            <input
              type="checkbox"
              checked={consentChecked}
              onChange={(e) => setConsentChecked(e.target.checked)}
              className="w-4 h-4 rounded border-slate-700 text-indigo-600 focus:ring-indigo-500/30 bg-slate-900 cursor-pointer"
            />
            <span className="text-xs font-medium text-slate-200 group-hover:text-white transition-colors">
              I consent to voice audio recording during this examination session.
            </span>
          </label>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            disabled={!micGranted || !consentChecked}
            onClick={onConsentAndProceed}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold text-white shadow-lg transition-all ${
              micGranted && consentChecked
                ? "bg-indigo-600 hover:bg-indigo-500 shadow-indigo-500/25 cursor-pointer"
                : "bg-slate-800 text-slate-500 cursor-not-allowed shadow-none"
            }`}
          >
            <Check className="w-4 h-4" />
            Enter Examination Room
          </button>
        </div>
      </div>
    </div>
  );
}
