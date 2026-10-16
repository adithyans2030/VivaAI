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
  // Tailored to Sage Celadon & Forest Pine aesthetic
  const config = {
    idle: {
      label: "Waiting to Begin",
      color: "from-[var(--border-default)] via-[var(--bg-card-subtle)] to-[var(--bg-card)]",
      glow: "shadow-black/10",
      border: "border-[var(--border-default)]",
      icon: Sparkles,
      iconColor: "text-[var(--text-muted)]",
      subtext: "Initiate your voice examination",
    },
    examiner_speaking: {
      label: "Examiner Speaking",
      color: "from-[#2D4F44] via-[#3E6B5D] to-[#6EA291]",
      glow: "shadow-[var(--accent-primary)]/40",
      border: "border-[#6EA291]/80",
      icon: Volume2,
      iconColor: "text-white",
      subtext: "Listen carefully to the question",
    },
    listening: {
      label: "Listening to Your Answer...",
      color: "from-[#1B4332] via-[#2D6A4F] to-[#74C69D]",
      glow: "shadow-emerald-500/40",
      border: "border-[#74C69D]/80",
      icon: Mic,
      iconColor: "text-white",
      subtext: "Speak naturally in your own words",
    },
    processing: {
      label: "Evaluating Understanding...",
      color: "from-[#2D4F44] via-[#D97706] to-[#6EA291]",
      glow: "shadow-amber-500/30",
      border: "border-amber-400/60",
      icon: Loader2,
      iconColor: "text-amber-200",
      subtext: "Analyzing response & grounded rubric",
    },
    completed: {
      label: "Viva Examination Completed",
      color: "from-[#1B4332] via-[#2D4F44] to-[#40916C]",
      glow: "shadow-emerald-500/30",
      border: "border-emerald-400/80",
      icon: CheckCircle2,
      iconColor: "text-white",
      subtext: "Review your comprehensive score report below",
    },
  }[state];

  const IconComponent = config.icon;

  // Calculate dynamic scale based on audio volume
  const dynamicScale = state === "listening" ? 1 + audioLevel * 0.35 : 1;

  return (
    <div
      onClick={onClick}
      className="flex flex-col items-center justify-center p-6 space-y-5 select-none relative group cursor-default"
    >
      {/* Outer ambient wave rings */}
      <div className="relative flex items-center justify-center">
        {state === "listening" && (
          <>
            <div
              className="absolute w-52 h-52 rounded-full border border-emerald-500/30 animate-ping pointer-events-none"
              style={{ animationDuration: "2.4s" }}
            />
            <div
              className="absolute w-44 h-44 rounded-full border border-emerald-400/40 animate-pulse-ring pointer-events-none"
              style={{ transform: `scale(${1 + audioLevel * 0.6})` }}
            />
          </>
        )}

        {state === "examiner_speaking" && (
          <div
            className="absolute w-44 h-44 rounded-full border border-[var(--border-focus)]/30 animate-pulse-ring pointer-events-none"
            style={{ animationDuration: "2s" }}
          />
        )}

        {/* Central Luminous Sphere */}
        <div
          className={`w-36 h-36 rounded-full bg-gradient-to-tr ${config.color} border-2 ${config.border} shadow-2xl ${config.glow} flex items-center justify-center transition-all duration-150 relative overflow-hidden backdrop-blur-md`}
          style={{ transform: `scale(${dynamicScale})` }}
        >
          {/* Inner glass glossy highlight */}
          <div className="absolute top-2 left-6 w-16 h-8 rounded-full bg-white/20 blur-xs -rotate-45 pointer-events-none" />

          {/* Icon */}
          <div className="relative z-10 flex items-center justify-center">
            <IconComponent
              className={`w-10 h-10 ${config.iconColor} ${
                state === "processing" ? "animate-spin" : ""
              }`}
            />
          </div>
        </div>
      </div>

      {/* State Label & Guidance */}
      <div className="text-center space-y-1">
        <div className="flex items-center justify-center gap-2">
          {state === "listening" && (
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          )}
          {state === "examiner_speaking" && (
            <span className="w-2 h-2 rounded-full bg-[var(--accent-primary)] animate-pulse" />
          )}
          <span className="text-sm font-semibold tracking-tight text-[var(--text-primary)]">
            {config.label}
          </span>
        </div>
        <p className="text-xs text-[var(--text-muted)] max-w-xs">{config.subtext}</p>
      </div>
    </div>
  );
}
