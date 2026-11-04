"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import BrandLogo from "@/components/BrandLogo";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import {
  Mail,
  Lock,
  ArrowRight,
  ShieldCheck,
  Mic,
  LayoutDashboard,
  Activity,
  Users,
} from "lucide-react";

const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

const demoCards = [
  {
    role: "teacher" as const,
    label: "Teacher Account",
    email: "teacher@vivaiq.edu",
    password: "TeacherPass123!",
    icon: LayoutDashboard,
    color: "var(--accent-1)",
    glow: "rgba(74, 158, 255, 0.15)",
    description: "Review sessions, override grades, upload syllabus",
  },
  {
    role: "student" as const,
    label: "Student Account",
    email: "alex@student.edu",
    password: "StudentPass123!",
    icon: Mic,
    color: "var(--accent-2)",
    glow: "rgba(59, 240, 170, 0.15)",
    description: "Start a voice viva, hear your feedback",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e?: React.FormEvent, override?: { email: string; password: string }) => {
    if (e) e.preventDefault();
    const creds = override ?? { email, password };

    if (!creds.email || !creds.password) {
      setError("Please provide your school email and password.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await api.login(creds.email, creds.password);
      const user = await api.getMe();
      router.push(user.role === "teacher" || user.role === "admin" ? "/teacher" : "/student");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed. Check credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex overflow-hidden"
      style={{ background: "var(--bg-base)" }}
    >
      {/* ── Left: Brand Panel ── */}
      <div
        className="force-dark hidden lg:flex w-[45%] relative flex-col justify-between p-14 overflow-hidden text-[var(--text-primary)]"
        style={{
          background: "linear-gradient(145deg, #070d14 0%, #0c1420 60%, #111e2d 100%)",
          borderRight: "1px solid var(--border-subtle)",
        }}
      >
        {/* Ambient orbs */}
        <div
          className="ambient-orb"
          style={{
            width: 400,
            height: 400,
            top: -100,
            right: -100,
            background: "var(--accent-1)",
            opacity: 0.12,
          }}
        />
        <div
          className="ambient-orb"
          style={{
            width: 300,
            height: 300,
            bottom: 80,
            left: -80,
            background: "var(--accent-2)",
            opacity: 0.08,
          }}
        />
        <div className="grid-pattern absolute inset-0 pointer-events-none" />

        {/* Logo */}
        <div className="relative z-10">
          <BrandLogo size="md" href="/" />
        </div>

        {/* Hero text */}
        <div className="relative z-10 space-y-6 my-auto">
          <div className="inline-flex items-center gap-2">
            <span
              className="w-6 h-px"
              style={{ background: "var(--text-muted)" }}
            />
            <span
              className="text-[10px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: "var(--text-muted)" }}
            >
              For the moments that matter
            </span>
          </div>

          <h1
            className="font-editorial text-5xl lg:text-6xl font-normal tracking-tight leading-[1.05]"
            style={{ color: "var(--text-primary)" }}
          >
            Make room
            <br />
            for what they
            <br />
            <em
              className="italic font-light"
              style={{
                background: "linear-gradient(135deg, var(--accent-1), var(--accent-2))",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              understand.
            </em>
          </h1>

          <p className="text-sm leading-relaxed max-w-sm" style={{ color: "var(--text-secondary)" }}>
            A thoughtful viva experience for students, with a clear and reviewable record for
            teachers. Powered by grounded AI voice and explainable acoustic assessment.
          </p>
        </div>

        {/* Trust badges */}
        <div className="relative z-10 flex flex-col gap-3">
          {[
            { icon: ShieldCheck, label: "Teacher-reviewed, always" },
            { icon: Activity, label: "Advisory authenticity signals" },
            { icon: Users, label: "GDPR-compliant data handling" },
          ].map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center gap-3">
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                style={{
                  background: "rgba(74, 158, 255, 0.08)",
                  border: "1px solid rgba(74, 158, 255, 0.15)",
                }}
              >
                <Icon className="w-3.5 h-3.5" style={{ color: "var(--accent-1)" }} />
              </div>
              <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right: Auth Form ── */}
      <div
        className="flex-1 flex flex-col items-center justify-center p-6 sm:p-10 relative overflow-y-auto"
        style={{ background: "var(--bg-surface)" }}
      >
        {/* Mobile logo */}
        <div className="lg:hidden mb-8">
          <BrandLogo size="lg" href="/" />
        </div>

        <div className="w-full max-w-[400px] space-y-6">
          {/* Header */}
          <div className="space-y-2">
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.18em]"
              style={{ color: "var(--text-muted)" }}
            >
              Welcome back
            </p>
            <h2
              className="font-editorial text-3xl sm:text-4xl font-normal tracking-tight"
              style={{ color: "var(--text-primary)" }}
            >
              Sign in to VivaIQ
            </h2>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Use your school account credentials to continue.
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="space-y-4">
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@school.edu"
              icon={<Mail className="w-4 h-4" />}
              required
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              icon={<Lock className="w-4 h-4" />}
              required
            />

            {error && (
              <div
                className="p-3.5 rounded-xl text-sm font-medium animate-fade-in-up"
                style={{
                  background: "var(--error-bg)",
                  border: "1px solid var(--error-border)",
                  color: "var(--error-text)",
                }}
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              size="md"
              isLoading={loading}
              className="w-full justify-between"
            >
              <span>Continue</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </form>

          {/* Demo accounts: only in demo builds, so credentials never ship to production. */}
          {isDemoMode && (
            <>
            {/* Divider */}
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px" style={{ background: "var(--border-subtle)" }} />
              <span className="text-[11px] font-medium" style={{ color: "var(--text-muted)" }}>
                OR TRY A DEMO
              </span>
              <div className="flex-1 h-px" style={{ background: "var(--border-subtle)" }} />
            </div>

            {/* Demo Quick-Access Cards */}
            <div className="grid grid-cols-2 gap-3">
              {demoCards.map(({ role, label, email: demoEmail, password: demoPass, icon: Icon, color, glow, description }) => (
                <button
                  key={role}
                  type="button"
                  onClick={() => {
                    setEmail(demoEmail);
                    setPassword(demoPass);
                    handleLogin(undefined, { email: demoEmail, password: demoPass });
                  }}
                  className="group p-4 rounded-2xl text-left transition-all duration-200 cursor-pointer"
                  style={{
                    background: glow,
                    border: `1px solid ${color}30`,
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.border = `1px solid ${color}60`;
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.border = `1px solid ${color}30`;
                  }}
                >
                  <div
                    className="w-8 h-8 rounded-xl flex items-center justify-center mb-3"
                    style={{ background: `${color}20`, border: `1px solid ${color}30` }}
                  >
                    <Icon className="w-4 h-4" style={{ color }} />
                  </div>
                  <div className="text-xs font-semibold mb-1" style={{ color: "var(--text-primary)" }}>
                    {label}
                  </div>
                  <div className="text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                    {description}
                  </div>
                </button>
              ))}
            </div>
            </>
          )}

          {/* Advisory footer */}
          <div
            className="flex items-start gap-3 p-3.5 rounded-xl"
            style={{
              background: "rgba(74, 158, 255, 0.04)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" style={{ color: "var(--accent-2)" }} />
            <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              Your assessment is advisory only — never an automated cheating accusation or final
              judgement. Teacher review is always required.
            </p>
          </div>

          <p className="text-center text-xs" style={{ color: "var(--text-muted)" }}>
            Need access?{" "}
            <span style={{ color: "var(--text-secondary)" }}>
              Ask your school administrator.
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}
