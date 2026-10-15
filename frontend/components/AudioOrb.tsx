"use client";

import React from "react";
import { Mic, Volume2, Loader2, Sparkles, CheckCircle2 } from "lucide-react";

export type ExaminerState =
  | "idle"
  | "examiner_speaking"
  | "listening"
  | "processing"
  | "completed";

interface AudioOrbProps {
  state: ExaminerState;
  audioLevel?: number; // 0 to 1
  onClick?: () => void;
}

export default function AudioOrb({ state, audioLevel = 0, onClick }: AudioOrbProps) {
  // Config per state
  const config = {
    idle: {
      label: "Waiting to Begin",
      color: "from-slate-700 via-indigo-900 to-slate-900",
      glow: "shadow-indigo-900/30",
      border: "border-slate-700/60",
      icon: Sparkles,
      iconColor: "text-slate-400",
      subtext: "Click or initiate voice session",
    },
    examiner_speaking: {
      label: "Examiner Speaking",
      color: "from-indigo-600 via-indigo-500 to-sky-400",
      glow: "shadow-indigo-500/50",
      border: "border-indigo-400/80",
      icon: Volume2,
      iconColor: "text-white",
      subtext: "Listen carefully to the question",
    },
    listening: {
      label: "Listening to Your Answer...",
      color: "from-emerald-600 via-teal-500 to-cyan-400",
      glow: "shadow-emerald-500/50",
      border: "border-emerald-400/80",
      icon: Mic,
      iconColor: "text-white",
      subtext: "Speak naturally in your own words",
    },
    processing: {
      label: "Evaluating Understanding...",
      color: "from-amber-600 via-violet-600 to-indigo-600",
      glow: "shadow-amber-500/40",
      border: "border-amber-400/70",
      icon: Loader2,
      iconColor: "text-amber-300",
      subtext: "Transcribing and scoring response",
    },
    completed: {
      label: "Viva Examination Completed",
      color: "from-emerald-600 via-teal-600 to-slate-800",
      glow: "shadow-emerald-500/40",
      border: "border-emerald-500",
      icon: CheckCircle2,
      iconColor: "text-emerald-300",
      subtext: "Review your detailed report below",
    },
  }[state];

  const IconComponent = config.icon;

  // Scale based on audio level
  const dynamicScale = state === "listening" ? 1 + audioLevel * 0.25 : 1;

  return (
    <div className="flex flex-col items-center justify-center p-6 select-none">
      {/* Outer Pulse Rings */}
      <div className="relative flex items-center justify-center cursor-pointer" onClick={onClick}>
        {/* Ambient Ring 1 */}
        <div
          className={`absolute w-64 h-64 rounded-full opacity-20 blur-xl bg-gradient-to-tr ${config.color} ${
            state === "examiner_speaking" || state === "listening" ? "animate-pulse" : ""
          }`}
        />

        {/* Dynamic Expanding Ring for speech */}
        {(state === "examiner_speaking" || state === "listening") && (
          <div
            className={`absolute w-52 h-52 rounded-full border-2 ${
              state === "listening" ? "border-emerald-400/40" : "border-indigo-400/40"
            } animate-ping opacity-30`}
          />
        )}

        {/* Middle decorative ring */}
        <div
          className={`absolute w-44 h-44 rounded-full border ${config.border} opacity-40 ${
            state === "processing" ? "animate-spin" : ""
          }`}
          style={{ animationDuration: "8s" }}
        />

        {/* Central Orb */}
        <div
          style={{ transform: `scale(${dynamicScale})`, transition: "transform 0.1s ease-out" }}
          className={`relative w-36 h-36 rounded-full bg-gradient-to-tr ${config.color} p-0.5 shadow-2xl ${config.glow} flex items-center justify-center transition-all duration-300`}
        >
          {/* Inner glass layer */}
          <div className="w-full h-full rounded-full bg-slate-950/40 backdrop-blur-md flex flex-col items-center justify-center gap-1.5 border border-white/20">
            <IconComponent
              className={`w-9 h-9 ${config.iconColor} ${
                state === "processing" ? "animate-spin" : ""
              }`}
            />
          </div>
        </div>
      </div>

      {/* Reactive Waveform Bars (shown while student is speaking) */}
      {state === "listening" && (
        <div className="flex items-center gap-1.5 h-10 mt-6">
          {[0.3, 0.7, 1.0, 0.6, 0.9, 0.4, 0.8, 0.5, 0.95, 0.6, 0.3].map((height, i) => (
            <div
              key={i}
              className="w-1.5 rounded-full bg-emerald-400 transition-all duration-75"
              style={{
                height: `${Math.max(6, height * 36 * (audioLevel > 0.05 ? audioLevel * 1.5 : 0.2))}px`,
                opacity: audioLevel > 0.05 ? 0.9 : 0.4,
              }}
            />
          ))}
        </div>
      )}

      {/* State Label & Subtext */}
      <div className="text-center mt-6">
        <h3 className="text-lg font-semibold tracking-tight text-white flex items-center justify-center gap-2">
          {config.label}
        </h3>
        <p className="text-xs text-slate-400 mt-1 max-w-sm">{config.subtext}</p>
      </div>
    </div>
  );
}
