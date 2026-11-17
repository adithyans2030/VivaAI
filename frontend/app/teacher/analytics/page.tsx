"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, VivaSession } from "@/lib/api";
import { ErrorBanner, PageHeader, card, errorText, isFinished, needsReview } from "@/components/teacher/shared";
import { AlertTriangle } from "lucide-react";

interface Stats {
  completed: number;
  unfinished: number;
  scored: number;
  average: number | null;
  students: number;
  flagged: number;
}

function summarize(sessions: VivaSession[]): Stats {
  const completed = sessions.filter(isFinished);
  const scored = completed.filter((s) => s.total_score != null);
  return {
    completed: completed.length,
    unfinished: sessions.length - completed.length,
    scored: scored.length,
    average: scored.length ? scored.reduce((sum, s) => sum + (s.total_score ?? 0), 0) / scored.length : null,
    students: new Set(sessions.map((s) => s.student_id)).size,
    flagged: sessions.filter(needsReview).length,
  };
}

export default function AnalyticsPage() {
  const [sessions, setSessions] = useState<VivaSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listSessions()
      .then((list) => !cancelled && setSessions(list))
      .catch((err) => !cancelled && setError(errorText(err, "Could not load sessions.")))
      .finally(() => !cancelled && setIsLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const overall = useMemo(() => summarize(sessions), [sessions]);
  const bySubject = useMemo(() => {
    const groups = new Map<string, { name: string; sessions: VivaSession[] }>();
    for (const s of sessions) {
      const g = groups.get(s.subject_id) ?? { name: s.subject_name || "Course viva", sessions: [] };
      g.sessions.push(s);
      groups.set(s.subject_id, g);
    }
    return [...groups.entries()]
      .map(([id, g]) => ({ id, name: g.name, stats: summarize(g.sessions) }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [sessions]);

  const tile = "p-5 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)]";

  return (
    <>
      <PageHeader title="Class Analytics" description="How your classes are doing across all vivas you can see." />
      {error && <ErrorBanner message={error} />}

      {isLoading ? (
        <div className={`${card} h-32 animate-pulse`} role="status" aria-label="Loading analytics" />
      ) : (
        <>
          <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className={tile}>
              <div className="text-xs text-[var(--text-secondary)] font-medium">Average score</div>
              <div className="font-editorial text-3xl text-[var(--text-primary)] mt-2">
                {overall.average != null ? overall.average.toFixed(1) : "—"}
                <span className="text-sm font-sans text-[var(--text-muted)]"> / 10</span>
              </div>
              <div className="text-[11px] text-[var(--text-muted)] mt-2">
                Across {overall.scored} scored viva{overall.scored === 1 ? "" : "s"}
              </div>
            </div>
            <div className={tile}>
              <div className="text-xs text-[var(--text-secondary)] font-medium">Completed vivas</div>
              <div className="font-editorial text-3xl text-[var(--text-primary)] mt-2">{overall.completed}</div>
              <div className="text-[11px] text-[var(--text-muted)] mt-2">
                {overall.students} student{overall.students === 1 ? "" : "s"} · {overall.unfinished} unfinished
              </div>
            </div>
            <div className={tile}>
              <div className="text-xs text-[var(--text-secondary)] font-medium">Needs review</div>
              <div className="font-editorial text-3xl text-[var(--text-primary)] mt-2">{overall.flagged}</div>
              <div className="text-[11px] text-amber-600 dark:text-amber-400 mt-2 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                Medium/high advisory flag: worth a conversation
              </div>
            </div>
          </section>

          <section className={`${card} overflow-x-auto`}>
            <table className="w-full text-sm">
              <caption className="text-left px-5 pt-5 pb-3 font-editorial text-lg text-[var(--text-primary)]">By subject</caption>
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] border-b border-[var(--border-default)]">
                  <th className="text-left font-semibold px-5 py-2">Subject</th>
                  <th className="text-right font-semibold px-3 py-2">Average</th>
                  <th className="text-right font-semibold px-3 py-2">Completed</th>
                  <th className="text-right font-semibold px-3 py-2">Unfinished</th>
                  <th className="text-right font-semibold px-5 py-2">Needs review</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-default)]">
                {bySubject.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-8 text-center text-[var(--text-muted)]">
                      No vivas yet.
                    </td>
                  </tr>
                ) : (
                  bySubject.map(({ id, name, stats }) => (
                    <tr key={id}>
                      <td className="px-5 py-3 text-[var(--text-primary)] font-medium">{name}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{stats.average != null ? stats.average.toFixed(1) : "—"}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{stats.completed}</td>
                      <td className="px-3 py-3 text-right tabular-nums text-[var(--text-muted)]">{stats.unfinished}</td>
                      <td className="px-5 py-3 text-right tabular-nums">
                        {stats.flagged > 0 ? (
                          <span className="text-amber-600 dark:text-amber-400 font-semibold">{stats.flagged}</span>
                        ) : (
                          0
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <p className="px-5 py-3 text-[11px] text-[var(--text-muted)] border-t border-[var(--border-default)]">
              Open <Link href="/teacher" className="text-[var(--accent-primary)] hover:underline">Viva Sessions</Link> and
              filter by &ldquo;Needs review&rdquo; to see the flagged sessions.
            </p>
          </section>
        </>
      )}
    </>
  );
}
