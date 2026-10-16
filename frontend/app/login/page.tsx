"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import BrandLogo from "@/components/BrandLogo";
import ThemeToggle from "@/components/ThemeToggle";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { Activity, ArrowRight, ShieldCheck } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e?: React.FormEvent, customEmail?: string, customPass?: string) => {
    if (e) e.preventDefault();
    const targetEmail = customEmail || email;
    const targetPass = customPass || password;

    if (!targetEmail || !targetPass) {
      setError("Please provide your school email and password.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await api.login(targetEmail, targetPass);
      const user = await api.getMe();
      if (user.role === "teacher" || user.role === "admin") {
        router.push("/teacher");
      } else {
        router.push("/student");
      }
    } catch (err: any) {
      setError(err.message || "HTTP 502 Bad Gateway");
    } finally {
      setLoading(false);
    }
  };

  const handleDemoFill = (role: "teacher" | "student") => {
    if (role === "teacher") {
      setEmail("teacher@vivaiq.edu");
      setPassword("teacher123");
      handleLogin(undefined, "teacher@vivaiq.edu", "teacher123");
    } else {
      setEmail("student@vivaiq.edu");
      setPassword("student123");
      handleLogin(undefined, "student@vivaiq.edu", "student123");
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row w-full bg-[var(--bg-surface)] text-[var(--text-primary)]">
      {/* ------------------------------------------------------------- */}
      {/* Left Pane: Editorial Brand & Manifesto Screen                 */}
      {/* ------------------------------------------------------------- */}
      <div className="w-full lg:w-1/2 min-h-[460px] lg:min-h-screen bg-[var(--bg-hero)] p-8 sm:p-12 lg:p-16 flex flex-col justify-between relative overflow-hidden">
        {/* Brand Header */}
        <div className="z-10">
          <BrandLogo size="md" />
        </div>

        {/* Hero Editorial Copy */}
        <div className="my-auto py-12 z-10 max-w-lg">
          <div className="flex items-center gap-2.5">
            <span className="w-6 h-[1.5px] bg-[var(--text-secondary)] opacity-80" />
            <span className="text-[10px] sm:text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-secondary)]">
              For the moments that matter
            </span>
          </div>

          <h1 className="font-editorial text-4xl sm:text-5xl lg:text-6xl text-[var(--text-primary)] font-normal tracking-tight leading-[1.08] mt-6">
            Make room<br />
            for what they<br />
            <em className="italic font-normal">understand.</em>
          </h1>

          <p className="text-sm sm:text-base text-[var(--text-secondary)] mt-6 leading-relaxed max-w-sm">
            A thoughtful viva experience for students, with a clear and reviewable record for teachers.
          </p>
        </div>

        {/* Ambient Concentric Wave Motif */}
        <div className="ambient-rings" aria-hidden="true" />

        {/* Footer Badges */}
        <div className="flex flex-wrap items-center gap-6 pt-6 z-10 text-xs text-[var(--text-secondary)]">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[var(--text-secondary)]" />
            <span>Teacher-reviewed, always</span>
          </div>
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-[var(--text-secondary)]" />
            <span>Service status operational</span>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* Right Pane: Authentication Form Area                          */}
      {/* ------------------------------------------------------------- */}
      <div className="w-full lg:w-1/2 min-h-screen bg-[var(--bg-surface)] p-6 sm:p-10 lg:p-16 flex flex-col justify-between relative">
        {/* Top bar with Theme Switcher */}
        <div className="w-full flex justify-end">
          <ThemeToggle />
        </div>

        {/* Centered Form */}
        <div className="w-full max-w-[390px] mx-auto my-auto py-8 space-y-6">
          <div className="space-y-1.5">
            <span className="text-[10px] sm:text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)] block">
              Welcome back
            </span>
            <h2 className="font-editorial text-3xl sm:text-4xl text-[var(--text-primary)] font-normal tracking-tight">
              Sign in to VivaIQ
            </h2>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)] mt-1">
              Use your school account to continue to your workspace.
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="space-y-4 pt-1">
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@school.edu"
              required
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />

            {error && (
              <div className="p-3.5 rounded-xl bg-[var(--error-bg)] border border-[var(--error-border)] text-xs font-medium text-[var(--error-text)] animate-in fade-in duration-200">
                {error}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={loading}
              className="w-full justify-between px-6"
            >
              <span>Continue</span>
              <ArrowRight className="w-4 h-4 ml-auto" />
            </Button>
          </form>

          {/* Demo Autofill Buttons */}
          <div className="space-y-2 pt-1">
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => handleDemoFill("teacher")}
              className="w-full text-xs font-semibold"
            >
              Fill teacher demo account
            </Button>

            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => handleDemoFill("student")}
              className="w-full text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            >
              Fill student demo account (Alex)
            </Button>
          </div>

          {/* Divider */}
          <div className="w-full h-[1px] bg-[var(--border-default)] pt-0 my-4" />

          {/* Advisory Guardrail Footnote */}
          <div className="flex items-start gap-2.5 text-left pt-1">
            <ShieldCheck className="w-4 h-4 text-[var(--text-secondary)] shrink-0 mt-0.5" />
            <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">
              Your assessment supports a conversation. It is advisory only, never a cheating detector or a final judgement.
            </p>
          </div>
        </div>

        {/* Footer Administrator Link */}
        <div className="text-center pb-2">
          <p className="text-xs text-[var(--text-muted)]">
            Need access? Ask your school administrator.
          </p>
        </div>
      </div>
    </div>
  );
}
