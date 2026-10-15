"use client";

import Link from "next/link";
import AudioOrb from "@/components/AudioOrb";
import {
  Mic,
  GraduationCap,
  LayoutDashboard,
  ShieldCheck,
  Brain,
  Sparkles,
  ArrowRight,
  FileCheck,
  Volume2,
  Cpu,
} from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col justify-between overflow-hidden">
      {/* Hero Section */}
      <section className="relative px-6 pt-16 pb-20 max-w-7xl mx-auto w-full">
        {/* Ambient background glows */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-gradient-to-tr from-indigo-600/20 via-sky-500/10 to-transparent blur-3xl pointer-events-none -z-10" />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Hero Content */}
          <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              Production-Grade Voice Viva Voce Examiner
            </div>

            <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white leading-tight">
              Calm, fair oral exams.{" "}
              <span className="bg-gradient-to-r from-indigo-400 via-sky-300 to-indigo-200 bg-clip-text text-transparent">
                Powered by AI Voice.
              </span>
            </h1>

            <p className="text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed">
              VivaIQ conducts voice viva examinations directly with students, asks probing follow-up questions grounded in uploaded course material, and provides teachers with rubric scores, transcripts, and an advisory authenticity assessment.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 pt-2">
              <Link
                href="/student"
                className="flex items-center gap-2.5 px-6 py-3.5 rounded-xl font-semibold text-sm text-white bg-indigo-600 hover:bg-indigo-500 shadow-xl shadow-indigo-600/30 transition-all cursor-pointer group"
              >
                <Mic className="w-4 h-4 group-hover:scale-110 transition-transform" />
                Launch Student Viva
                <ArrowRight className="w-4 h-4 ml-1" />
              </Link>

              <Link
                href="/teacher"
                className="flex items-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-sm text-slate-200 bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 transition-all cursor-pointer"
              >
                <LayoutDashboard className="w-4 h-4 text-emerald-400" />
                Teacher Dashboard
              </Link>

              <Link
                href="/login"
                className="flex items-center gap-1.5 px-4 py-3.5 rounded-xl font-medium text-xs text-slate-400 hover:text-slate-200 transition-colors"
              >
                One-Click Demo Accounts →
              </Link>
            </div>
          </div>

          {/* Right Hero Interactive Orb Showcase */}
          <div className="lg:col-span-5 flex justify-center">
            <div className="glass-panel p-8 rounded-3xl border border-slate-800/80 shadow-2xl relative w-full max-w-md">
              <div className="absolute top-4 right-4 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-semibold border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Voice Pipeline Live
              </div>

              <AudioOrb state="examiner_speaking" audioLevel={0.6} />

              <div className="mt-4 p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 text-center text-xs text-slate-300">
                <span className="text-indigo-400 font-semibold block mb-0.5">Sample Examiner Turn:</span>
                "Explain how mutual exclusion prevents race conditions in multi-threaded programs."
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Pillars */}
      <section className="px-6 py-16 border-t border-slate-800/60 max-w-7xl mx-auto w-full">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Brain className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">RAG-Grounded Questioning</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Examinations strictly cite topics, syllabus notes, and textbook excerpts uploaded by course professors.
            </p>
          </div>

          {/* Card 2 */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">Advisory Authenticity Engine</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Analyzes pause rhythms, verbatim overlap, and prosodic dynamics against student baselines. Always advisory, never auto-penalizing.
            </p>
          </div>

          {/* Card 3 */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
              <Cpu className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white">Provider Agnostic Core</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Runs seamlessly on consumer GPUs (NVIDIA GTX 1650 4GB) with local Ollama or scales to Gemini / Grok by configuration alone.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800/60 py-6 px-6 text-center text-xs text-slate-500">
        VivaIQ Voice Viva Voce System • Engineered with Next.js, FastAPI, faster-whisper, and ChromaDB.
      </footer>
    </div>
  );
}
