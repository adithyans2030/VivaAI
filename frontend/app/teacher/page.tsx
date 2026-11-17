"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Subject, VivaSession } from "@/lib/api";
import Button from "@/components/ui/Button";
import {
  ErrorBanner,
  FlagBadge,
  PageHeader,
  StatusBadge,
  card,
  errorText,
  fieldClass,
  formatDateTime,
  formatScore,
  isFinished,
  needsReview,
} from "@/components/teacher/shared";
import { ChevronRight, RefreshCw, Search } from "lucide-react";

type StatusFilter = "all" | "completed" | "unfinished" | "review";

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "review", label: "Needs review" },
  { value: "completed", label: "Completed" },
  { value: "unfinished", label: "Unfinished" },
];

export default function TeacherSessionsPage() {
  const [sessions, setSessions] = useState<VivaSession[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [subjectId, setSubjectId] = useState("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const [sessList, subjList] = await Promise.all([api.listSessions(), api.listSubjects()]);
      setSessions(sessList);
      setSubjects(subjList);
    } catch (err) {
      setLoadError(
        errorText(err, "Unable to reach the VivaIQ server. Check that the backend is running and you are signed in as a teacher.")
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void loadData(), 0);
    return () => clearTimeout(timer);
  }, [loadData]);

  const counts = useMemo(
    () => ({
      all: sessions.length,
      completed: sessions.filter(isFinished).length,
      unfinished: sessions.filter((s) => !isFinished(s)).length,
      review: sessions.filter(needsReview).length,
    }),
    [sessions]
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sessions
      .filter((s) => subjectId === "all" || s.subject_id === subjectId)
      .filter((s) => {
        if (statusFilter === "completed") return isFinished(s);
        if (statusFilter === "unfinished") return !isFinished(s);
        if (statusFilter === "review") return needsReview(s);
        return true;
      })
      .filter(
        (s) =>
          !q ||
          (s.student_name || "").toLowerCase().includes(q) ||
          (s.subject_name || "").toLowerCase().includes(q) ||
          (s.subject_code || "").toLowerCase().includes(q)
      )
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [sessions, query, subjectId, statusFilter]);

  return (
    <>
      <PageHeader
        title="Viva Sessions"
        description="Every student examination. Open one to hear the answers, read transcripts, add notes or adjust the grade."
        actions={
          <Button className="gap-1.5" size="sm" variant="outline" onClick={loadData} isLoading={isLoading}>
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        }
      />

      {loadError && <ErrorBanner message={loadError} />}

      {/* Filters */}
      <div className={`${card} p-4 space-y-3`}>
        <div className="flex flex-col sm:flex-row gap-3">
          <label className="relative flex-1">
            <span className="sr-only">Search sessions</span>
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="search"
              placeholder="Search student or subject…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className={`${fieldClass} pl-9`}
            />
          </label>
          <label className="sm:w-64">
            <span className="sr-only">Subject</span>
            <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className={fieldClass}>
              <option value="all">All subjects</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} · {s.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by status">
          {STATUS_FILTERS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setStatusFilter(value)}
              aria-pressed={statusFilter === value}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                statusFilter === value
                  ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)]"
                  : "bg-[var(--bg-card-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {label} <span className="opacity-70">({counts[value]})</span>
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      {isLoading && sessions.length === 0 ? (
        <div className="space-y-2" role="status" aria-label="Loading sessions">
          {[0, 1, 2].map((i) => (
            <div key={i} className={`${card} h-[68px] animate-pulse`} />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className={`${card} p-10 text-center text-sm text-[var(--text-muted)]`}>
          {sessions.length === 0
            ? "No viva sessions yet. When students take a viva it will appear here."
            : "No sessions match these filters."}
        </div>
      ) : (
        <ul className={`${card} divide-y divide-[var(--border-default)] overflow-hidden`}>
          {visible.map((s) => (
            <li key={s.id}>
              <Link
                href={`/teacher/sessions/${s.id}`}
                className="flex items-center gap-4 px-4 py-3.5 hover:bg-[var(--bg-card-subtle)] transition-colors focus-visible:outline-none focus-visible:bg-[var(--bg-card-subtle)]"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-[var(--text-primary)] truncate">
                    {s.student_name || "Student"}
                  </div>
                  <div className="text-xs text-[var(--text-secondary)] truncate">
                    {s.subject_name || "Course viva"} · {formatDateTime(s.created_at)}
                  </div>
                  <div className="flex sm:hidden gap-1.5 mt-1.5">
                    <StatusBadge status={s.status} />
                    <FlagBadge session={s} />
                  </div>
                </div>
                <div className="hidden sm:flex items-center gap-2">
                  <StatusBadge status={s.status} />
                  <FlagBadge session={s} />
                </div>
                <div className="w-14 text-right font-editorial text-lg text-[var(--text-primary)]">
                  {isFinished(s) ? formatScore(s.total_score) : "—"}
                </div>
                <ChevronRight className="w-4 h-4 text-[var(--text-muted)] shrink-0" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
