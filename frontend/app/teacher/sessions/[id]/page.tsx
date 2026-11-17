"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api, VivaSession } from "@/lib/api";
import type { AuthenticityLevel } from "@/lib/ws";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import TurnAudio from "@/components/TurnAudio";
import {
  ErrorBanner,
  FlagBadge,
  StatusBadge,
  card,
  errorText,
  fieldClass,
  formatDateTime,
  formatScore,
  isFinished,
} from "@/components/teacher/shared";
import { ArrowLeft, Download, Edit3, Info, Save, ShieldAlert, X } from "lucide-react";

export default function SessionDetailPage() {
  // The session id is only known at request time, so it must be read inside Suspense (cacheComponents).
  return (
    <Suspense fallback={<div className={`${card} h-40 animate-pulse`} role="status" aria-label="Loading session" />}>
      <SessionDetail />
    </Suspense>
  );
}

function SessionDetail() {
  const { id } = useParams<{ id: string }>();
  const [session, setSession] = useState<VivaSession | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [notes, setNotes] = useState("");
  const [isSavingNotes, setIsSavingNotes] = useState(false);
  const [notesSaved, setNotesSaved] = useState(false);

  const [isOverrideOpen, setIsOverrideOpen] = useState(false);
  const [overrideScore, setOverrideScore] = useState("");
  const [overrideFlag, setOverrideFlag] = useState<AuthenticityLevel>("low");
  const [overrideReason, setOverrideReason] = useState("");

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const detail = await api.getSession(id);
      setSession(detail);
      setNotes(detail.teacher_notes || "");
    } catch (err) {
      setLoadError(errorText(err, "Could not load this session."));
    }
  }, [id]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [load]);

  const handleSaveNotes = async () => {
    setIsSavingNotes(true);
    setActionError(null);
    try {
      await api.updateTeacherNotes(id, notes);
      setNotesSaved(true);
      setTimeout(() => setNotesSaved(false), 2500);
    } catch (err) {
      setActionError(`Failed to save notes: ${errorText(err)}`);
    } finally {
      setIsSavingNotes(false);
    }
  };

  const openOverride = () => {
    if (!session) return;
    setOverrideScore(session.total_score != null ? String(session.total_score) : "");
    setOverrideFlag(session.overall_authenticity_likelihood === "unknown" ? "low" : session.overall_authenticity_likelihood);
    setOverrideReason("");
    setIsOverrideOpen(true);
  };

  const parsedScore = Number(overrideScore);
  const scoreValid = overrideScore !== "" && Number.isFinite(parsedScore) && parsedScore >= 0 && parsedScore <= 10;

  const handleApplyOverride = async () => {
    if (!session || !scoreValid || !overrideReason.trim()) return;
    setActionError(null);
    try {
      await api.overrideScore(id, { new_score: parsedScore, new_authenticity: overrideFlag, reason: overrideReason.trim() });
      setSession({ ...session, total_score: parsedScore, overall_authenticity_likelihood: overrideFlag });
      setIsOverrideOpen(false);
    } catch (err) {
      setActionError(`Failed to apply override: ${errorText(err)}`);
    }
  };

  const exportAs = (format: "csv" | "pdf") =>
    void api.downloadSessionExport(id, format).catch((err) => setActionError(`Export ${format.toUpperCase()} failed: ${errorText(err)}`));

  return (
    <>
      <Link
        href="/teacher"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        All sessions
      </Link>

      {loadError && <ErrorBanner message={loadError} />}
      {actionError && <ErrorBanner message={actionError} onDismiss={() => setActionError(null)} />}

      {!session ? (
        !loadError && <div className={`${card} h-40 animate-pulse`} role="status" aria-label="Loading session" />
      ) : (
        <>
          {/* Overview */}
          <section className={`${card} p-5 sm:p-6 space-y-5`}>
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
              <div>
                <h1 className="font-editorial text-2xl sm:text-3xl font-normal text-[var(--text-primary)]">
                  {session.student_name || "Student"}
                </h1>
                <p className="text-sm text-[var(--text-secondary)] mt-1">
                  {session.subject_name || "Course viva"} · {formatDateTime(session.created_at)}
                </p>
                <div className="flex flex-wrap gap-2 mt-3">
                  <StatusBadge status={session.status} />
                  <FlagBadge session={session} />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button className="gap-1.5" variant="outline" size="sm" onClick={openOverride}>
                  <Edit3 className="w-3.5 h-3.5" />
                  Override grade
                </Button>
                <Button className="gap-1.5" variant="outline" size="sm" onClick={() => exportAs("csv")}>
                  <Download className="w-3.5 h-3.5" />
                  CSV
                </Button>
                <Button className="gap-1.5" variant="outline" size="sm" onClick={() => exportAs("pdf")}>
                  <Download className="w-3.5 h-3.5" />
                  PDF
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)]">
                <div className="text-[11px] text-[var(--text-secondary)] uppercase font-semibold tracking-wider">Score</div>
                <div className="font-editorial text-3xl text-[var(--text-primary)] mt-1">
                  {isFinished(session) || session.total_score != null ? formatScore(session.total_score) : "Not finished"}
                </div>
                <div className="text-[11px] text-[var(--text-muted)] mt-1">
                  Correctness, completeness, clarity and depth; the warm-up is not scored.
                </div>
              </div>
              <div className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)]">
                <div className="text-[11px] text-[var(--text-secondary)] uppercase font-semibold tracking-wider">
                  Advisory authenticity
                </div>
                <div className="font-editorial text-2xl capitalize text-[var(--text-primary)] mt-1">
                  {isFinished(session) && session.overall_authenticity_likelihood !== "unknown"
                    ? `${session.overall_authenticity_likelihood} likelihood`
                    : "Not assessed"}
                </div>
                <div className="text-[11px] text-[var(--text-muted)] mt-1">
                  {session.overall_authenticity_confidence != null
                    ? `Confidence ${Math.round(session.overall_authenticity_confidence * 100)}%`
                    : "Assessed when the viva is completed"}
                </div>
              </div>
            </div>

            {session.overall_authenticity_reasons && session.overall_authenticity_reasons.length > 0 && (
              <div className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] space-y-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)]">
                  <ShieldAlert className="w-4 h-4 text-[var(--accent-primary)]" />
                  Why this flag
                </div>
                <ul className="text-xs text-[var(--text-secondary)] space-y-1.5 list-disc list-inside">
                  {session.overall_authenticity_reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
                <div className="pt-2 border-t border-[var(--border-default)] flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
                  <Info className="w-3.5 h-3.5 shrink-0" />
                  Advisory only: a prompt for a conversation, never a cheating verdict.
                </div>
              </div>
            )}
          </section>

          {/* Turns */}
          <section className={`${card} p-5 sm:p-6 space-y-4`}>
            <div className="flex items-center justify-between">
              <h2 className="font-editorial text-lg text-[var(--text-primary)]">Questions & answers</h2>
              <span className="text-xs text-[var(--text-muted)]">{session.turns?.length || 0} questions</span>
            </div>
            {!session.turns?.length ? (
              <p className="text-sm text-[var(--text-muted)]">No questions were asked in this session.</p>
            ) : (
              <ol className="space-y-4">
                {session.turns.map((turn) => (
                  <li key={turn.id} className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <span className="text-xs font-semibold text-[var(--text-secondary)]">
                        Q{turn.turn_number} · {turn.topic}
                        <span className="font-normal text-[var(--text-muted)]"> ({turn.question_type})</span>
                      </span>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-[var(--bg-card)] border border-[var(--border-default)] text-[var(--text-primary)] shrink-0">
                        {turn.question_type === "warmup"
                          ? "Warm-up · not scored"
                          : turn.score_0_10 != null
                            ? `${turn.score_0_10}/10`
                            : "Not graded"}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-[var(--text-primary)]">&ldquo;{turn.question_text}&rdquo;</p>
                    <div className="p-3 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] text-sm text-[var(--text-secondary)]">
                      <span className="text-[10px] text-[var(--text-muted)] uppercase font-semibold tracking-wider block mb-1">
                        Student&rsquo;s answer
                      </span>
                      {turn.transcript ? <span className="italic">&ldquo;{turn.transcript}&rdquo;</span> : "Not answered"}
                    </div>
                    {turn.transcript && <TurnAudio sessionId={session.id} turnId={turn.id} />}
                    {turn.feedback && <p className="text-xs text-[var(--text-secondary)]">Feedback: {turn.feedback}</p>}
                  </li>
                ))}
              </ol>
            )}
          </section>

          {/* Notes */}
          <section className={`${card} p-5 sm:p-6 space-y-3`}>
            <div className="flex items-center justify-between">
              <h2 className="font-editorial text-base text-[var(--text-primary)]">Teacher notes</h2>
              {notesSaved && <span className="text-xs text-emerald-600 dark:text-emerald-400">✓ Saved</span>}
            </div>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Private observations, praise, or follow-up for this student…"
              className={fieldClass}
            />
            <div className="flex justify-end">
              <Button className="gap-1.5" size="sm" onClick={handleSaveNotes} isLoading={isSavingNotes}>
                <Save className="w-3.5 h-3.5" />
                Save notes
              </Button>
            </div>
          </section>
        </>
      )}

      {isOverrideOpen && session && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="override-title"
        >
          <div className={`${card} w-full max-w-md p-6 space-y-5 shadow-2xl`}>
            <div className="flex items-center justify-between">
              <div>
                <Badge variant="eyebrow" className="mb-1">
                  Logged in the audit trail
                </Badge>
                <h3 id="override-title" className="font-editorial text-xl text-[var(--text-primary)]">
                  Override grade
                </h3>
              </div>
              <button
                onClick={() => setIsOverrideOpen(false)}
                aria-label="Close"
                className="p-1 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-[var(--text-secondary)]">New score (0–10)</span>
              <input
                type="number"
                step="0.1"
                min="0"
                max="10"
                value={overrideScore}
                onChange={(e) => setOverrideScore(e.target.value)}
                className={fieldClass}
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-[var(--text-secondary)]">Advisory authenticity flag</span>
              <select
                value={overrideFlag}
                onChange={(e) => setOverrideFlag(e.target.value as AuthenticityLevel)}
                className={fieldClass}
              >
                <option value="low">Low (spontaneous answer)</option>
                <option value="medium">Medium (possibly reading)</option>
                <option value="high">High (likely reading a script)</option>
              </select>
            </label>
            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-[var(--text-secondary)]">Reason (required)</span>
              <textarea
                rows={2}
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="e.g. Discussed with student in person; answer was their own."
                className={fieldClass}
              />
            </label>
            <div className="flex justify-end gap-2">
              <Button className="gap-1.5" variant="ghost" size="sm" onClick={() => setIsOverrideOpen(false)}>
                Cancel
              </Button>
              <Button className="gap-1.5" size="sm" onClick={handleApplyOverride} disabled={!scoreValid || !overrideReason.trim()}>
                Save override
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
