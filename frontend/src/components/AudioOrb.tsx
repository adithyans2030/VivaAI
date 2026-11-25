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

const orbConfig = {
  idle: {
    label: "Ready to Begin",
    sublabel: "Initiate your voice examination",
    icon: Sparkles,
    gradient: "linear-gradient(145deg, #1a2740 0%, #1f3050 50%, #162238 100%)",
    glow: "rgba(74, 158, 255, 0.1)",
    border: "rgba(74, 158, 255, 0.2)",
    iconColor: "var(--text-muted)",
    dotColor: "var(--text-muted)",
  },
  examiner_speaking: {
    label: "Examiner Speaking",
    sublabel: "Listen carefully to the question",
    icon: Volume2,
    gradient: "linear-gradient(145deg, #0d2744 0%, #1a4a80 50%, #0d3361 100%)",
    glow: "rgba(74, 158, 255, 0.45)",
    border: "rgba(74, 158, 255, 0.6)",
    iconColor: "#4a9eff",
    dotColor: "#4a9eff",
  },
  listening: {
    label: "Listening to You...",
    sublabel: "Speak naturally in your own words",
    icon: Mic,
    gradient: "linear-gradient(145deg, #0a3020 0%, #155235 50%, #0e3a28 100%)",
    glow: "rgba(59, 240, 170, 0.45)",
    border: "rgba(59, 240, 170, 0.6)",
    iconColor: "#3bf0aa",
    dotColor: "#3bf0aa",
  },
  processing: {
    label: "Evaluating Response...",
    sublabel: "Analyzing against grounded rubric",
    icon: Loader2,
    gradient: "linear-gradient(145deg, #2a1a0d 0%, #4a3010 50%, #1e1408 100%)",
    glow: "rgba(251, 191, 36, 0.35)",
    border: "rgba(251, 191, 36, 0.5)",
    iconColor: "#fbbf24",
    dotColor: "#fbbf24",
  },
  completed: {
    label: "Viva Completed",
    sublabel: "Review your score report below",
    icon: CheckCircle2,
    gradient: "linear-gradient(145deg, #0a3020 0%, #1a5535 50%, #0a2d1e 100%)",
    glow: "rgba(59, 240, 170, 0.3)",
    border: "rgba(59, 240, 170, 0.55)",
    iconColor: "#3bf0aa",
    dotColor: "#3bf0aa",
  },
} as const;

export default function AudioOrb({ state, audioLevel = 0, onClick }: AudioOrbProps) {
  const cfg = orbConfig[state];
  const IconComponent = cfg.icon;

  // Dynamic ring scale based on audio level
  const dynamicScale = state === "listening" ? 1 + audioLevel * 0.3 : 1;

  return (
    <div
      onClick={onClick}
      className="flex flex-col items-center justify-center space-y-5 select-none relative group"
    >
      {/* Outer glow rings */}
      <div className="relative flex items-center justify-center">
        {/* Ambient glow ring — always present */}
        <div
          className="absolute rounded-full pointer-events-none transition-all duration-500"
          style={{
            width: 200,
            height: 200,
            background: `radial-gradient(ellipse, ${cfg.glow} 0%, transparent 70%)`,
          }}
        />

        {/* Pulse ring for active states */}
        {(state === "examiner_speaking" || state === "listening") && (
          <div
            className="absolute rounded-full border animate-pulse-ring pointer-events-none"
            style={{
              width: 172,
              height: 172,
              borderColor: cfg.border,
              opacity: 0.5,
              animationDuration: state === "listening" ? "2s" : "2.8s",
            }}
          />
        )}

        {/* Audio-reactive ring for listening */}
        {state === "listening" && (
          <div
            className="absolute rounded-full border pointer-events-none transition-transform duration-75"
            style={{
              width: 148,
              height: 148,
              borderColor: cfg.border,
              transform: `scale(${1 + audioLevel * 0.5})`,
              opacity: 0.3 + audioLevel * 0.5,
            }}
          />
        )}

        {/* Central Orb */}
        <div
          className="relative w-32 h-32 rounded-full flex items-center justify-center transition-transform duration-150 overflow-hidden"
          style={{
            background: cfg.gradient,
            border: `1.5px solid ${cfg.border}`,
            boxShadow: `0 0 40px ${cfg.glow}, 0 8px 32px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.08)`,
            transform: `scale(${dynamicScale})`,
          }}
        >
          {/* Gloss highlight */}
          <div
            className="absolute rounded-full pointer-events-none"
            style={{
              width: 64,
              height: 28,
              top: 10,
              left: 14,
              background: "rgba(255,255,255,0.12)",
              filter: "blur(6px)",
              transform: "rotate(-30deg)",
            }}
          />

          {/* Inner glow */}
          <div
            className="absolute inset-0 rounded-full pointer-events-none"
            style={{
              background: `radial-gradient(ellipse at 35% 35%, ${cfg.glow} 0%, transparent 60%)`,
            }}
          />

          {/* Icon */}
          <div className="relative z-10">
            <IconComponent
              className={state === "processing" ? "animate-spin" : ""}
              style={{
                width: 38,
                height: 38,
                color: cfg.iconColor,
                filter: `drop-shadow(0 0 8px ${cfg.glow})`,
              }}
            />
          </div>
        </div>
      </div>

      {/* Labels */}
      <div className="text-center space-y-1.5">
        <div className="flex items-center justify-center gap-2">
          {(state === "listening" || state === "examiner_speaking") && (
            <span
              className="w-2 h-2 rounded-full animate-beacon shrink-0"
              style={{ background: cfg.dotColor }}
            />
          )}
          <span
            className="text-sm font-semibold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            {cfg.label}
          </span>
        </div>
        <p className="text-xs max-w-[200px]" style={{ color: "var(--text-muted)" }}>
          {cfg.sublabel}
        </p>
      </div>
    </div>
  );
}
