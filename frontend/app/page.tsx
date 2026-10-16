"use client";

import Link from "next/link";
import AudioOrb from "@/components/AudioOrb";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import {
  Mic,
  LayoutDashboard,
  ShieldCheck,
  Brain,
  Sparkles,
  ArrowRight,
  FileCheck,
  Cpu,
  CheckCircle2,
  Lock,
  Activity,
} from "lucide-react";

export default function HomePage() {
  return (
    <div className="relative min-h-[calc(100vh-65px)] flex flex-col justify-between overflow-hidden">
      {/* Editorial Hero Section */}
      <section className="relative px-6 pt-12 md:pt-20 pb-16 max-w-7xl mx-auto w-full">
        {/* Ambient Wave Rings Motif */}
        <div className="ambient-rings opacity-70 hidden md:block" />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
          {/* Left Column: Manifesto & Value Proposition */}
          <div className="lg:col-span-7 space-y-6 text-left">
            <div className="flex items-center gap-3">
              <span className="w-6 h-px bg-[var(--text-secondary)] opacity-60" />
              <Badge variant="eyebrow">For the moments that matter</Badge>
            </div>

            <h1 className="font-editorial text-4xl sm:text-6xl md:text-7xl font-normal text-[var(--text-primary)] leading-[1.08] tracking-tight">
              Make room <br />
              for what they <br />
              <em className="italic font-normal">understand.</em>
            </h1>

            <p className="text-base sm:text-lg text-[var(--text-secondary)] max-w-xl leading-relaxed">
              A thoughtful viva experience for students, with a clear and reviewable record for teachers. Powered by grounded AI voice and explainable acoustic assessment.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-3.5 pt-3">
              <Link href="/student">
                <Button size="lg" className="group">
                  <Mic className="w-4 h-4 group-hover:scale-110 transition-transform" />
                  Launch Student Viva
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </Link>

              <Link href="/teacher">
                <Button variant="outline" size="lg">
                  <LayoutDashboard className="w-4 h-4 text-[var(--accent-primary)]" />
                  Teacher Review Portal
                </Button>
              </Link>

              <Link href="/login">
                <Button variant="ghost" size="lg">
                  Demo Sign-In →
                </Button>
              </Link>
            </div>

            {/* Guardrail Disclaimer */}
            <div className="flex flex-wrap items-center gap-6 pt-4 text-xs text-[var(--text-muted)]">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span>Teacher-reviewed, always</span>
              </div>
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-[var(--accent-primary)]" />
                <span>Advisory authenticity analysis</span>
              </div>
            </div>
          </div>

          {/* Right Column: Audio Orb Live Preview Showcase */}
          <div className="lg:col-span-5 flex justify-center">
            <div className="w-full max-w-md p-8 rounded-3xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xl relative overflow-hidden">
              {/* Subtle status eyebrow */}
              <div className="flex items-center justify-between pb-6 border-b border-[var(--border-default)]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                    Voice Viva In Progress
                  </span>
                </div>
                <span className="text-[11px] text-[var(--text-muted)] font-mono">
                  TURN 2 OF 4
                </span>
              </div>

              {/* The Harmonic Orb */}
              <div className="py-6 flex justify-center">
                <AudioOrb state="examiner_speaking" audioLevel={0.65} />
              </div>

              {/* Spoken Turn Excerpt */}
              <div className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] space-y-1.5 text-left">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-primary)] block">
                  Examiner Question:
                </span>
                <p className="text-xs text-[var(--text-primary)] font-medium leading-relaxed">
                  "Explain how mutual exclusion prevents race conditions in multi-threaded programs."
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Pillars */}
      <section className="px-6 py-16 border-t border-[var(--border-default)] max-w-7xl mx-auto w-full">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] space-y-3 text-left">
            <div className="w-10 h-10 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] flex items-center justify-center text-[var(--accent-primary)]">
              <Brain className="w-5 h-5" />
            </div>
            <h3 className="font-editorial text-lg font-normal text-[var(--text-primary)]">
              RAG-Grounded Questioning
            </h3>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Examinations strictly cite topics, syllabus notes, and textbook excerpts uploaded by course professors. No generic hallucinated prompts.
            </p>
          </div>

          {/* Card 2 */}
          <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] space-y-3 text-left">
            <div className="w-10 h-10 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] flex items-center justify-center text-[var(--accent-primary)]">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="font-editorial text-lg font-normal text-[var(--text-primary)]">
              Advisory Authenticity Engine
            </h3>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Analyzes conversational pause rhythms, 4-gram textbook overlap, and vocal cadence against baseline speech. Always advisory, never auto-penalizing.
            </p>
          </div>

          {/* Card 3 */}
          <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] space-y-3 text-left">
            <div className="w-10 h-10 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] flex items-center justify-center text-[var(--accent-primary)]">
              <Cpu className="w-5 h-5" />
            </div>
            <h3 className="font-editorial text-lg font-normal text-[var(--text-primary)]">
              Local Hardware or Cloud AI
            </h3>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Runs locally on consumer GPUs (NVIDIA GTX 1650 4GB) with local Ollama (`gemma2:2b`), or connects smoothly to Gemini and Grok.
            </p>
          </div>
        </div>
      </section>

      {/* Advisory Policy Banner & Footer */}
      <footer className="border-t border-[var(--border-default)] py-8 px-6 text-center text-xs text-[var(--text-muted)] space-y-2">
        <div className="flex items-center justify-center gap-2 max-w-xl mx-auto">
          <ShieldCheck className="w-4 h-4 text-[var(--accent-primary)] shrink-0" />
          <span>
            Your assessment supports a conversation. It is advisory only, never a cheating detector or a final judgement.
          </span>
        </div>
        <div className="pt-2 text-[11px] opacity-75">
          VivaIQ Oral Viva Voce System • Next.js, FastAPI, faster-whisper, and ChromaDB.
        </div>
      </footer>
    </div>
  );
}
