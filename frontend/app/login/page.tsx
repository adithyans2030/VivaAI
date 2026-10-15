"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Sparkles, GraduationCap, LayoutDashboard, Shield, AlertCircle, ArrowRight, Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (loginEmail?: string, loginPass?: string) => {
    const targetEmail = loginEmail || email;
    const targetPass = loginPass || password;

    if (!targetEmail || !targetPass) {
      setError("Please provide both email and password");
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
      setError(err.message || "Failed to log in");
    } finally {
      setLoading(false);
    }
  };

  const loginAsDemo = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    handleLogin(demoEmail, demoPass);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-radial from-slate-900 via-slate-950 to-black">
      <div className="w-full max-w-md space-y-6">
        {/* Brand */}
        <div className="text-center space-y-2">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-sky-400 items-center justify-center shadow-xl shadow-indigo-500/25 mb-1">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            Viva<span className="text-indigo-400">IQ</span>
          </h1>
          <p className="text-xs text-slate-400 max-w-xs mx-auto">
            AI-Powered Oral Viva Voce Examiner & Explainable Authenticity Assessor
          </p>
        </div>

        {/* Demo Fast-Login Cards */}
        <div className="glass-panel p-4 rounded-2xl border border-slate-800/80 space-y-2.5">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1">
            ⚡ Quick Demo Accounts (One-Click)
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => loginAsDemo("student@vivaiq.edu", "student123")}
              disabled={loading}
              className="flex items-center gap-2.5 p-3 rounded-xl bg-slate-800/40 hover:bg-indigo-600/20 border border-slate-700/60 hover:border-indigo-500/40 text-left transition-all group"
            >
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center text-indigo-400 group-hover:scale-105 transition-transform">
                <GraduationCap className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-semibold text-slate-200">Ada Lovelace</div>
                <div className="text-[10px] text-indigo-400 font-medium">Student Role</div>
              </div>
            </button>

            <button
              onClick={() => loginAsDemo("teacher@vivaiq.edu", "teacher123")}
              disabled={loading}
              className="flex items-center gap-2.5 p-3 rounded-xl bg-slate-800/40 hover:bg-emerald-600/20 border border-slate-700/60 hover:border-emerald-500/40 text-left transition-all group"
            >
              <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform">
                <LayoutDashboard className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-semibold text-slate-200">Prof. Turing</div>
                <div className="text-[10px] text-emerald-400 font-medium">Teacher Role</div>
              </div>
            </button>
          </div>
        </div>

        {/* Credentials Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleLogin();
          }}
          className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4 shadow-2xl"
        >
          {error && (
            <div className="flex items-center gap-2 p-3 text-xs text-rose-300 bg-rose-500/10 rounded-xl border border-rose-500/20">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. student@vivaiq.edu"
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700/80 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700/80 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-semibold text-xs text-white bg-indigo-600 hover:bg-indigo-500 shadow-lg shadow-indigo-600/25 transition-all cursor-pointer disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <span>Sign In to VivaIQ</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <p className="text-center text-xs text-slate-500">
          Academic credentials secured with bcrypt and tokenized JWT.
        </p>
      </div>
    </div>
  );
}
