import { Link } from "react-router";
import AudioOrb from "@/components/AudioOrb";
import Button from "@/components/ui/Button";
import {
  Mic,
  LayoutDashboard,
  ShieldCheck,
  Brain,
  ArrowRight,
  Cpu,
  Activity,
  BookOpen,
  Zap,
  Lock,
  ChevronRight,
} from "lucide-react";

const features = [
  {
    icon: Brain,
    title: "RAG-Grounded Questioning",
    description:
      "Every question strictly grounded in your uploaded syllabus, lecture notes, and textbooks. Zero hallucinated prompts.",
    color: "var(--accent-1)",
    glow: "rgba(74, 158, 255, 0.2)",
  },
  {
    icon: ShieldCheck,
    title: "Advisory Authenticity",
    description:
      "Acoustic cadence analysis, pause rhythms, and 4-gram overlap signals. Always advisory — never an automated verdict.",
    color: "var(--accent-2)",
    glow: "rgba(59, 240, 170, 0.2)",
  },
  {
    icon: Cpu,
    title: "Local or Cloud AI",
    description:
      "Runs on consumer GPUs with Ollama or connects to Gemini/Grok. Full provider-agnostic architecture.",
    color: "var(--accent-3)",
    glow: "rgba(155, 109, 255, 0.2)",
  },
];

const stats = [
  { value: "6", label: "Authenticity signals", unit: "" },
  { value: "4", label: "Scoring dimensions", unit: "" },
  { value: "<800", label: "MB VRAM required", unit: "MB" },
  { value: "100%", label: "Teacher-reviewed", unit: "" },
];

export default function HomePage() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* ── Ambient background orbs ── */}
      <div
        className="ambient-orb ambient-orb-blue"
        style={{ width: 600, height: 600, top: "-200px", right: "-150px", opacity: 0.15 }}
      />
      <div
        className="ambient-orb ambient-orb-violet"
        style={{ width: 400, height: 400, bottom: "200px", left: "-100px", opacity: 0.1 }}
      />
      <div
        className="ambient-orb ambient-orb-green"
        style={{ width: 300, height: 300, top: "60%", right: "10%", opacity: 0.08 }}
      />

      {/* ── Grid overlay ── */}
      <div className="grid-pattern absolute inset-0 pointer-events-none" />

      {/* ════════════════════════════════════════════════════════════
          HERO
      ════════════════════════════════════════════════════════════ */}
      <section className="relative pt-20 pb-24 px-5 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* ── Left: Copy ── */}
          <div className="lg:col-span-6 space-y-8">
            {/* Pill badge */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-[var(--border-emphasis)] bg-[var(--bg-card)]">
              <span
                className="w-1.5 h-1.5 rounded-full animate-beacon"
                style={{ background: "var(--accent-2)" }}
              />
              <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-accent)]">
                AI Voice Examiner — Beta
              </span>
            </div>

            {/* Headline */}
            <div className="space-y-2">
              <h1
                className="font-editorial text-5xl sm:text-6xl lg:text-7xl font-normal leading-[1.05] tracking-tight"
                style={{ color: "var(--text-primary)" }}
              >
                Make room
                <br />
                for what they
                <br />
                <em
                  className="italic font-light not-italic"
                  style={{
                    background: "linear-gradient(135deg, var(--accent-1), var(--accent-2))",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  understand.
                </em>
              </h1>
            </div>

            {/* Subtitle */}
            <p
              className="text-base sm:text-lg leading-relaxed max-w-md"
              style={{ color: "var(--text-secondary)" }}
            >
              A production-grade AI viva voce platform. Real voice interactions, grounded grading,
              and advisory authenticity analysis — without replacing teacher judgment.
            </p>

            {/* CTA row */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link to="/student">
                <Button size="lg" className="group">
                  <Mic className="w-4 h-4 transition-transform group-hover:scale-110" />
                  Start Student Viva
                  <ArrowRight className="w-4 h-4 ml-1 transition-transform group-hover:translate-x-0.5" />
                </Button>
              </Link>

              <Link to="/teacher">
                <Button variant="secondary" size="lg">
                  <LayoutDashboard className="w-4 h-4" style={{ color: "var(--accent-1)" }} />
                  Teacher Portal
                </Button>
              </Link>

              <Link to="/login">
                <Button variant="ghost" size="lg">
                  Demo Sign-In
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </Link>
            </div>

            {/* Trust badges */}
            <div className="flex flex-wrap items-center gap-5 pt-1">
              {[
                { icon: ShieldCheck, text: "Teacher-reviewed, always", color: "var(--accent-2)" },
                { icon: Activity, text: "Advisory signals only", color: "var(--accent-1)" },
                { icon: Lock, text: "Local or cloud AI", color: "var(--accent-3)" },
              ].map(({ icon: Icon, text, color }) => (
                <div key={text} className="flex items-center gap-1.5">
                  <Icon className="w-3.5 h-3.5" style={{ color }} />
                  <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                    {text}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* ── Right: Live Preview Card ── */}
          <div className="lg:col-span-6 flex justify-center lg:justify-end">
            <div
              className="w-full max-w-[420px] rounded-3xl overflow-hidden relative"
              style={{
                background:
                  "linear-gradient(145deg, rgba(17,30,45,0.95) 0%, rgba(11,20,32,0.98) 100%)",
                border: "1px solid var(--border-emphasis)",
                boxShadow:
                  "0 32px 80px -16px rgba(0,0,0,0.7), 0 0 0 1px var(--border-subtle), inset 0 1px 0 rgba(255,255,255,0.06)",
              }}
            >
              {/* Card header */}
              <div
                className="flex items-center justify-between px-5 py-4 border-b"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                <div className="flex items-center gap-2.5">
                  <span className="w-2 h-2 rounded-full animate-beacon" style={{ background: "var(--accent-2)" }} />
                  <span
                    className="text-[11px] font-semibold uppercase tracking-[0.14em]"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Viva In Progress
                  </span>
                </div>
                <div
                  className="font-mono text-[11px] px-2.5 py-1 rounded-lg"
                  style={{
                    color: "var(--accent-1)",
                    background: "rgba(74, 158, 255, 0.1)",
                    border: "1px solid rgba(74, 158, 255, 0.2)",
                  }}
                >
                  TURN 2 / 4
                </div>
              </div>

              {/* Orb */}
              <div className="py-8 flex justify-center">
                <AudioOrb state="examiner_speaking" audioLevel={0.65} />
              </div>

              {/* Question card */}
              <div className="px-5 pb-5">
                <div
                  className="p-4 rounded-2xl"
                  style={{
                    background: "rgba(74, 158, 255, 0.06)",
                    border: "1px solid rgba(74, 158, 255, 0.15)",
                  }}
                >
                  <div
                    className="text-[10px] font-semibold uppercase tracking-[0.14em] mb-2"
                    style={{ color: "var(--accent-1)" }}
                  >
                    Examiner Question
                  </div>
                  <p
                    className="text-sm leading-relaxed"
                    style={{ color: "var(--text-primary)" }}
                  >
                    &ldquo;Explain how mutual exclusion prevents race conditions in multi-threaded programs.&rdquo;
                  </p>
                </div>
              </div>

              {/* Waveform footer */}
              <div
                className="flex items-center justify-center gap-[3px] px-5 pb-5 h-12"
                aria-hidden="true"
              >
                {[4, 7, 5, 9, 6, 11, 8, 5, 7, 9, 6, 4, 8, 10, 6, 5, 7, 9].map((h, i) => (
                  <div
                    key={i}
                    className="animate-wave-bar rounded-full"
                    style={{
                      width: 3,
                      height: h * 2,
                      background: "linear-gradient(to top, var(--accent-1), var(--accent-2))",
                      animationDelay: `${i * 0.07}s`,
                      opacity: 0.6,
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════
          STATS
      ════════════════════════════════════════════════════════════ */}
      <section
        className="border-y px-5 py-12"
        style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}
      >
        <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8">
          {stats.map(({ value, label }) => (
            <div key={label} className="text-center space-y-1">
              <div
                className="text-3xl font-bold tracking-tight"
                style={{
                  background: "linear-gradient(135deg, var(--accent-1), var(--accent-2))",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                {value}
              </div>
              <div className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════
          FEATURES
      ════════════════════════════════════════════════════════════ */}
      <section className="relative px-5 py-24 max-w-7xl mx-auto">
        {/* Section header */}
        <div className="text-center space-y-3 mb-14">
          <div
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-semibold uppercase tracking-[0.14em]"
            style={{
              color: "var(--text-muted)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <Zap className="w-3 h-3" />
            Platform Features
          </div>
          <h2
            className="font-editorial text-3xl sm:text-4xl font-normal tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            Built for real academic rigor
          </h2>
          <p className="text-sm max-w-lg mx-auto leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            Every design decision prioritizes fairness to students and transparency to teachers.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {features.map(({ icon: Icon, title, description, color, glow }) => (
            <div
              key={title}
              className="glass-card p-6 rounded-2xl space-y-4"
            >
              <div
                className="w-11 h-11 rounded-xl flex items-center justify-center"
                style={{
                  background: `${glow}`,
                  border: `1px solid ${color}30`,
                  boxShadow: `0 0 20px ${glow}`,
                }}
              >
                <Icon className="w-5 h-5" style={{ color }} />
              </div>
              <h3
                className="font-semibold text-base tracking-tight"
                style={{ color: "var(--text-primary)" }}
              >
                {title}
              </h3>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════
          CTA BAND
      ════════════════════════════════════════════════════════════ */}
      <section
        className="px-5 py-16 text-center relative overflow-hidden"
        style={{
          background:
            "linear-gradient(145deg, rgba(74,158,255,0.08) 0%, rgba(59,240,170,0.06) 50%, rgba(155,109,255,0.05) 100%)",
          borderTop: "1px solid var(--border-subtle)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div className="max-w-2xl mx-auto space-y-6">
          <h2
            className="font-editorial text-3xl sm:text-4xl font-normal tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            Ready to conduct a fairer viva?
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            Set up takes minutes. Sign in and run your first AI-assisted voice examination today.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link to="/login">
              <Button size="lg" className="group">
                Get Started Now
                <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-0.5 transition-transform" />
              </Button>
            </Link>
            <Link to="/teacher">
              <Button variant="outline" size="lg">
                <BookOpen className="w-4 h-4" />
                See Teacher Portal
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════
          FOOTER
      ════════════════════════════════════════════════════════════ */}
      <footer className="py-8 px-5 text-center space-y-3" style={{ borderTop: "1px solid var(--border-subtle)" }}>
        <div
          className="flex items-center justify-center gap-2 max-w-xl mx-auto text-xs"
          style={{ color: "var(--text-muted)" }}
        >
          <ShieldCheck className="w-4 h-4 shrink-0" style={{ color: "var(--accent-2)" }} />
          <span>
            Authenticity signals are advisory only — never an automated accusation or final verdict.
            Teacher review is always required.
          </span>
        </div>
        <div className="text-[11px]" style={{ color: "var(--text-muted)", opacity: 0.6 }}>
          VivaIQ Oral Viva Voce System · React · Vite · FastAPI · faster-whisper · ChromaDB
        </div>
      </footer>
    </div>
  );
}
