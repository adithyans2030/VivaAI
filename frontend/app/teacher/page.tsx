"use client";

import { useCallback, useEffect, useState } from "react";
import { api, Subject, VivaSession, DocumentItem } from "@/lib/api";
import type { AuthenticityLevel } from "@/lib/ws";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import TurnAudio from "@/components/TurnAudio";
import {
  Search,
  Filter,
  ShieldAlert,
  AlertTriangle,
  Download,
  Edit3,
  UploadCloud,
  FileText,
  Clock,
  CheckCircle2,
  Info,
  Save,
  X,
} from "lucide-react";

export default function TeacherDashboardPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [sessions, setSessions] = useState<VivaSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<VivaSession | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [activeTab, setActiveTab] = useState<"sessions" | "documents" | "analytics">("sessions");

  // Filters
  const [filterFlag, setFilterFlag] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // UI Status & Error States
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Grade & Flag Override Modal
  const [isOverrideOpen, setIsOverrideOpen] = useState(false);
  const [overrideScore, setOverrideScore] = useState<number>(8.5);
  const [overrideFlag, setOverrideFlag] = useState<AuthenticityLevel>("low");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [teacherNotes, setTeacherNotes] = useState<string>("");
  const [isSavingNotes, setIsSavingNotes] = useState(false);
  const [notesSavedSuccess, setNotesSavedSuccess] = useState(false);

  // List rows carry no turns; fetch the full record (questions, transcripts, rubric, reasons).
  const selectSession = useCallback(async (s: VivaSession) => {
    setSelectedSession(s);
    setTeacherNotes(s.teacher_notes || "");
    try {
      const detail = await api.getSession(s.id);
      setSelectedSession((current) => (current?.id === s.id ? detail : current));
    } catch (err) {
      setActionError(`Could not load session details: ${(err instanceof Error && err.message) || "Server error"}`);
    }
  }, []);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const [subjList, sessList] = await Promise.all([
        api.listSubjects(),
        api.listSessions(),
      ]);
      setSubjects(subjList);
      setSessions(sessList);

      if (subjList.length > 0) {
        api.listDocuments(subjList[0].id).then(setDocuments).catch(() => {});
      }
      if (sessList.length > 0) {
        await selectSession(sessList[0]);
      }
    } catch (err) {
      setSessions([]);
      setSubjects([]);
      setSelectedSession(null);
      setLoadError(
        (err instanceof Error && err.message) ||
          "Unable to connect to VivaIQ server. Please verify the backend is running and that you are logged in as a teacher."
      );
    } finally {
      setIsLoading(false);
    }
  }, [selectSession]);

  useEffect(() => {
    // Fetch on mount; state updates happen after the request resolves.
    const timer = setTimeout(() => void loadData(), 0);
    return () => clearTimeout(timer);
  }, [loadData]);

  // Upload Document Handler
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || subjects.length === 0) return;
    setActionError(null);

    try {
      await api.uploadDocument(subjects[0].id, file);
      const updatedDocs = await api.listDocuments(subjects[0].id);
      setDocuments(updatedDocs);
    } catch (err) {
      setActionError(`Document upload failed: ${(err instanceof Error && err.message) || "Ensure the backend is online and document conforms to accepted types (PDF/TXT/MD <= 25MB)."}`);
    }
  };

  // Override Submission
  const handleApplyOverride = async () => {
    if (!selectedSession) return;
    setActionError(null);
    try {
      await api.overrideScore(selectedSession.id, {
        new_score: overrideScore,
        new_authenticity: overrideFlag,
        reason: overrideReason || "Teacher manual review",
      });
      const updated: VivaSession = {
        ...selectedSession,
        total_score: overrideScore,
        overall_authenticity_likelihood: overrideFlag,
      };
      setSelectedSession(updated);
      setSessions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setIsOverrideOpen(false);
    } catch (err) {
      setActionError(`Failed to apply score override: ${(err instanceof Error && err.message) || "Server error"}`);
    }
  };

  // Save Teacher Notes
  const handleSaveNotes = async () => {
    if (!selectedSession) return;
    setIsSavingNotes(true);
    setActionError(null);
    try {
      await api.updateTeacherNotes(selectedSession.id, teacherNotes);
      setNotesSavedSuccess(true);
      setTimeout(() => setNotesSavedSuccess(false), 2500);
    } catch (err) {
      setActionError(`Failed to save notes: ${(err instanceof Error && err.message) || "Server error"}`);
    } finally {
      setIsSavingNotes(false);
    }
  };

  // Class analytics, computed from the sessions this teacher can see.
  const completedSessions = sessions.filter((s) => s.status === "completed");
  const scored = completedSessions.filter((s) => s.total_score != null);
  const classStats = {
    completedCount: completedSessions.length,
    scoredCount: scored.length,
    averageScore: scored.length ? scored.reduce((sum, s) => sum + (s.total_score ?? 0), 0) / scored.length : null,
    studentCount: new Set(sessions.map((s) => s.student_id)).size,
    flaggedCount: completedSessions.filter(
      (s) => s.overall_authenticity_likelihood === "medium" || s.overall_authenticity_likelihood === "high"
    ).length,
  };

  // Filtered Sessions
  const filteredSessions = sessions.filter((s) => {
    const studentName = s.student_name || "Candidate";
    const subjectName = s.subject_name || "";
    const matchesQuery =
      studentName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      subjectName.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesFlag =
      filterFlag === "all" || s.overall_authenticity_likelihood === filterFlag;

    return matchesQuery && matchesFlag;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 md:py-12 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 pb-6 border-b border-[var(--border-default)]">
        <div>
          <Badge variant="eyebrow" className="mb-2">
            Teacher Workspace • Oral Records & Review
          </Badge>
          <h1 className="font-editorial text-3xl sm:text-4xl font-normal text-[var(--text-primary)] tracking-tight">
            Examiner Review & Oversight
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1.5 max-w-2xl leading-relaxed">
            Review live spoken transcripts, rubric grading evidence, and advisory 6-signal authenticity metrics. All assessments are strictly advisory to support teacher judgment.
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] self-start lg:self-auto">
          <button
            onClick={() => setActiveTab("sessions")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "sessions"
                ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]"
            }`}
          >
            Viva Sessions ({sessions.length})
          </button>
          <button
            onClick={() => setActiveTab("documents")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "documents"
                ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]"
            }`}
          >
            Course Material (RAG)
          </button>
          <button
            onClick={() => setActiveTab("analytics")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "analytics"
                ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]"
            }`}
          >
            Class Analytics
          </button>
        </div>
      </div>

      {/* Status & Error Alerts */}
      {loadError && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-400 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-500" />
            <span>{loadError}</span>
          </div>
          <Button size="sm" variant="outline" onClick={loadData} className="ml-4 shrink-0 text-xs">
            Retry Connection
          </Button>
        </div>
      )}

      {actionError && (
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-400 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-amber-500" />
            <span>{actionError}</span>
          </div>
          <button onClick={() => setActionError(null)} className="ml-2 font-bold hover:opacity-80">
            ✕
          </button>
        </div>
      )}


      {/* SESSIONS TAB */}
      {activeTab === "sessions" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Filter & Session Roster */}
          <div className="lg:col-span-5 space-y-4">
            {/* Search & Filter Bar */}
            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs space-y-3">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  placeholder="Search candidate or subject..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 text-xs rounded-xl border border-[var(--border-default)] bg-[var(--bg-card-subtle)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--border-focus)] transition-all"
                />
              </div>

              {/* Authenticity Filter Pills */}
              <div className="flex items-center gap-1.5 pt-2 border-t border-[var(--border-default)]">
                <Filter className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                <span className="text-[11px] text-[var(--text-secondary)] font-medium">Flag:</span>
                {["all", "low", "medium", "high"].map((level) => (
                  <button
                    key={level}
                    onClick={() => setFilterFlag(level)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold capitalize transition-all cursor-pointer ${
                      filterFlag === level
                        ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)]"
                        : "text-[var(--text-secondary)] hover:bg-[var(--bg-card-subtle)]"
                    }`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>

            {/* Candidate Session List */}
            <div className="space-y-2.5">
              {isLoading ? (
                <div className="space-y-2.5" role="status" aria-label="Loading sessions">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="h-[76px] rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] animate-pulse"
                    />
                  ))}
                </div>
              ) : filteredSessions.length === 0 ? (
                <div className="p-8 text-center rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] text-xs text-[var(--text-muted)]">
                  {sessions.length === 0
                    ? "No viva sessions yet. Completed examinations will appear here."
                    : "No sessions match current search and flag filters."}
                </div>
              ) : (
                filteredSessions.map((s) => {
                  const isSelected = selectedSession?.id === s.id;
                  const isLowRisk = s.overall_authenticity_likelihood === "low";
                  const isMedRisk = s.overall_authenticity_likelihood === "medium";

                  return (
                    <div
                      key={s.id}
                      role="button"
                      tabIndex={0}
                      aria-pressed={isSelected}
                      onClick={() => void selectSession(s)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          void selectSession(s);
                        }
                      }}
                      className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                        isSelected
                          ? "bg-[var(--bg-card)] border-[var(--border-focus)] shadow-sm ring-1 ring-[var(--border-focus)]"
                          : "bg-[var(--bg-card)] border-[var(--border-default)] hover:border-[var(--border-focus)] hover:bg-[var(--bg-card-subtle)]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                              {s.student_name || "Candidate"}
                            </h4>
                            {isSelected && (
                              <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)]" />
                            )}
                          </div>
                          <div className="text-xs text-[var(--text-secondary)] mt-0.5">
                            {s.subject_name || "Course Viva"}
                          </div>
                          <div className="text-[11px] text-[var(--text-muted)] flex items-center gap-1.5 mt-2">
                            <Clock className="w-3 h-3" />
                            {new Date(s.created_at).toLocaleDateString(undefined, {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </div>
                        </div>

                        <div className="text-right flex flex-col items-end">
                          <div className="font-editorial text-lg font-normal text-[var(--text-primary)]">
                            {s.total_score ? `${s.total_score}/10` : "Pending"}
                          </div>
                          <span
                            className={`mt-1.5 px-2.5 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider ${
                              isLowRisk
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                                : isMedRisk
                                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                                : "bg-[var(--error-bg)] text-[var(--error-text)] border border-[var(--error-border)]"
                            }`}
                          >
                            {s.overall_authenticity_likelihood} Flag
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Column: Detailed Candidate Inspector */}
          {selectedSession ? (
            <div className="lg:col-span-7 space-y-6">
              {/* Candidate Overview Card */}
              <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <Badge variant="eyebrow" className="mb-1">
                      Candidate Examination Record
                    </Badge>
                    <h2 className="font-editorial text-2xl font-normal text-[var(--text-primary)]">
                      {selectedSession.student_name || "Candidate"}
                    </h2>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                      {selectedSession.subject_name} • Oral Viva Voce
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setOverrideScore(selectedSession.total_score || 8.0);
                        setOverrideFlag(selectedSession.overall_authenticity_likelihood || "low");
                        setIsOverrideOpen(true);
                      }}
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      Override Grade
                    </Button>
                    <button
                      type="button"
                      onClick={() =>
                        void api
                          .downloadSessionExport(selectedSession.id, "csv")
                          .catch((err) =>
                            setActionError(`Export CSV failed: ${(err instanceof Error && err.message) || "Server error"}`)
                          )
                      }
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-[var(--accent-primary)] text-[var(--accent-contrast)] hover:bg-[var(--accent-hover)] transition-all shadow-xs cursor-pointer"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Export CSV
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        void api
                          .downloadSessionExport(selectedSession.id, "pdf")
                          .catch((err) =>
                            setActionError(`Export PDF failed: ${(err instanceof Error && err.message) || "Server error"}`)
                          )
                      }
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-[var(--accent-primary)] text-[var(--accent-contrast)] hover:bg-[var(--accent-hover)] transition-all shadow-xs cursor-pointer"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Export PDF
                    </button>
                  </div>
                </div>

                {/* Score & Authenticity Metrics Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)]">
                    <div className="text-[11px] text-[var(--text-secondary)] uppercase font-semibold tracking-wider">
                      Rubric Examination Score
                    </div>
                    <div className="font-editorial text-3xl font-normal text-[var(--text-primary)] mt-1">
                      {selectedSession.total_score}{" "}
                      <span className="text-sm font-sans text-[var(--text-muted)]">/ 10</span>
                    </div>
                    <div className="text-[11px] text-[var(--text-secondary)] mt-1 flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                      Grounded on 4 rubric dimensions
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)]">
                    <div className="text-[11px] text-[var(--text-secondary)] uppercase font-semibold tracking-wider">
                      Advisory Authenticity Likelihood
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="font-editorial text-2xl font-normal capitalize text-[var(--text-primary)]">
                        {selectedSession.overall_authenticity_likelihood} Likelihood
                      </span>
                    </div>
                    <div className="text-[11px] text-[var(--text-muted)] mt-1">
                      {selectedSession.overall_authenticity_confidence != null
                        ? `Confidence: ${Math.round(selectedSession.overall_authenticity_confidence * 100)}%`
                        : "Not yet assessed"}
                    </div>
                  </div>
                </div>

                {/* 6-Signal Advisory Authenticity Evidence */}
                {selectedSession.overall_authenticity_reasons && (
                  <div className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] space-y-2.5">
                    <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)]">
                      <ShieldAlert className="w-4 h-4 text-[var(--accent-primary)]" />
                      Advisory Acoustic & Textual Findings:
                    </div>
                    <ul className="text-xs text-[var(--text-secondary)] space-y-1.5 list-disc list-inside">
                      {selectedSession.overall_authenticity_reasons.map((r, i) => (
                        <li key={i} className="leading-relaxed">{r}</li>
                      ))}
                    </ul>
                    <div className="pt-2 border-t border-[var(--border-default)] flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
                      <Info className="w-3.5 h-3.5 shrink-0" />
                      <span>
                        Advisory only. Designed to guide instructor conversation, never an automated penalty or cheating verdict.
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Spoken Turns & Transcripts */}
              <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-editorial text-lg font-normal text-[var(--text-primary)]">
                    Question Turns & Spoken Transcripts
                  </h3>
                  <span className="text-xs text-[var(--text-muted)]">
                    {selectedSession.turns?.length || 0} turns recorded
                  </span>
                </div>

                <div className="space-y-4">
                  {selectedSession.turns?.map((turn) => (
                    <div
                      key={turn.id}
                      className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-[var(--text-secondary)] flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)]" />
                          Turn #{turn.turn_number}: {turn.topic} ({turn.question_type})
                        </span>
                        <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-[var(--bg-card)] border border-[var(--border-default)] text-[var(--text-primary)]">
                          {turn.question_type === "warmup"
                            ? "Warm-up · not scored"
                            : turn.score_0_10 != null
                              ? `${turn.score_0_10}/10`
                              : "Not graded"}
                        </span>
                      </div>

                      <p className="text-xs font-medium text-[var(--text-primary)] leading-relaxed">
                        &ldquo;{turn.question_text}&rdquo;
                      </p>

                      <div className="p-3 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] text-xs text-[var(--text-secondary)] italic leading-relaxed">
                        <span className="text-[10px] text-[var(--text-muted)] uppercase not-italic font-semibold tracking-wider block mb-1">
                          Student&rsquo;s Spoken Answer:
                        </span>
                        {turn.transcript ? <>&ldquo;{turn.transcript}&rdquo;</> : <span className="not-italic">Not answered</span>}
                      </div>

                      {turn.transcript && <TurnAudio sessionId={selectedSession.id} turnId={turn.id} />}

                      <div className="text-[11px] text-[var(--text-secondary)] border-t border-[var(--border-default)] pt-2 flex items-center justify-between">
                        <span>Feedback: {turn.feedback || "—"}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Teacher Notes & Audit Trail */}
              <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-editorial text-base font-normal text-[var(--text-primary)]">
                    Teacher Evaluation Notes
                  </h3>
                  {notesSavedSuccess && (
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium animate-in fade-in">
                      ✓ Notes saved
                    </span>
                  )}
                </div>

                <textarea
                  rows={3}
                  value={teacherNotes}
                  onChange={(e) => setTeacherNotes(e.target.value)}
                  placeholder="Record confidential teacher observations, student praise, or recommended follow-up..."
                  className="w-full p-3.5 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--border-focus)] transition-all"
                />

                <div className="flex justify-end">
                  <Button
                    size="sm"
                    onClick={handleSaveNotes}
                    isLoading={isSavingNotes}
                  >
                    <Save className="w-3.5 h-3.5" />
                    Save Notes
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="lg:col-span-7 p-12 text-center rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] text-sm text-[var(--text-muted)]">
              Select a candidate session from the roster to view their oral examination record.
            </div>
          )}
        </div>
      )}

      {/* DOCUMENTS TAB (COURSE MATERIAL / RAG) */}
      {activeTab === "documents" && (
        <div className="p-6 sm:p-8 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <Badge variant="eyebrow" className="mb-1">
                Grounded Questioning Pipeline
              </Badge>
              <h2 className="font-editorial text-2xl font-normal text-[var(--text-primary)]">
                Course Materials & Textbooks
              </h2>
              <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-xl">
                Uploaded PDFs, lecture slides, and notes are chunked and embedded via ChromaDB. The voice examiner formulates grounded oral questions strictly from these documents.
              </p>
            </div>

            <label className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[var(--accent-primary)] text-[var(--accent-contrast)] hover:bg-[var(--accent-hover)] text-xs font-semibold cursor-pointer transition-all shadow-xs self-start sm:self-auto">
              <UploadCloud className="w-4 h-4" />
              Upload Course Material
              <input type="file" onChange={handleUpload} className="hidden" accept=".pdf,.docx,.txt,.md" />
            </label>
          </div>

          <div className="space-y-3 pt-2">
            {documents.length === 0 ? (
              <div className="text-center py-12 text-[var(--text-muted)] text-xs border border-dashed border-[var(--border-default)] rounded-xl">
                No course material uploaded yet. Upload lecture notes, textbook chapters, or syllabi.
              </div>
            ) : (
              documents.map((doc) => (
                <div
                  key={doc.id}
                  className="p-4 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] flex items-center justify-between"
                >
                  <div className="flex items-center gap-3.5">
                    <div className="w-9 h-9 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] flex items-center justify-center text-[var(--accent-primary)]">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-[var(--text-primary)]">{doc.filename}</div>
                      <div className="text-[11px] text-[var(--text-muted)]">
                        {doc.chunk_count} semantic chunks • {(doc.file_size_bytes / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>

                  <span className="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 capitalize">
                    {doc.ingestion_status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* CLASS ANALYTICS TAB */}
      {activeTab === "analytics" && (
        <div className="p-6 sm:p-8 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs space-y-6">
          <div>
            <Badge variant="eyebrow" className="mb-1">
              Cohort Intelligence
            </Badge>
            <h2 className="font-editorial text-2xl font-normal text-[var(--text-primary)]">
              Class Performance & Topic Mastery
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Aggregated insights across all completed candidate examinations in this course.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-5 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)]">
              <div className="text-xs text-[var(--text-secondary)] font-medium">Class Average Score</div>
              <div className="font-editorial text-3xl font-normal text-[var(--text-primary)] mt-2">
                {classStats.averageScore != null ? classStats.averageScore.toFixed(1) : "—"}{" "}
                <span className="text-sm font-sans text-[var(--text-muted)]">/ 10</span>
              </div>
              <div className="text-[11px] text-[var(--text-muted)] mt-2">
                Mean of {classStats.scoredCount} scored viva{classStats.scoredCount === 1 ? "" : "s"}
              </div>
            </div>

            <div className="p-5 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)]">
              <div className="text-xs text-[var(--text-secondary)] font-medium">Total Completed Vivas</div>
              <div className="font-editorial text-3xl font-normal text-[var(--text-primary)] mt-2">
                {classStats.completedCount}
              </div>
              <div className="text-[11px] text-[var(--text-muted)] mt-2">
                {classStats.studentCount} student{classStats.studentCount === 1 ? "" : "s"} •{" "}
                {sessions.length - classStats.completedCount} not finished
              </div>
            </div>

            <div className="p-5 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)]">
              <div className="text-xs text-[var(--text-secondary)] font-medium">Advisory Authenticity Flags</div>
              <div className="font-editorial text-3xl font-normal text-[var(--text-primary)] mt-2">
                {classStats.flaggedCount}{" "}
                <span className="text-sm font-sans text-[var(--text-muted)]">
                  session{classStats.flaggedCount === 1 ? "" : "s"}
                </span>
              </div>
              <div className="text-[11px] text-amber-600 dark:text-amber-400 mt-2 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                Medium or high: advisory, worth a conversation
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Grade & Flag Override Modal */}
      {isOverrideOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-2xl space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <Badge variant="eyebrow" className="mb-1">
                  Manual Override Audit
                </Badge>
                <h3 className="font-editorial text-xl font-normal text-[var(--text-primary)]">
                  Override Examination Grade
                </h3>
              </div>
              <button
                onClick={() => setIsOverrideOpen(false)}
                className="p-1 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-subtle)] transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="space-y-1.5 text-left">
                <label className="block text-xs font-medium text-[var(--text-secondary)]">
                  Revised Score (0 - 10)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="10"
                  value={overrideScore}
                  onChange={(e) => setOverrideScore(parseFloat(e.target.value))}
                  className="w-full px-4 py-2.5 text-xs rounded-xl border border-[var(--border-default)] bg-[var(--bg-card-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--border-focus)]"
                />
              </div>

              <div className="space-y-1.5 text-left">
                <label className="block text-xs font-medium text-[var(--text-secondary)]">
                  Revised Advisory Authenticity Flag
                </label>
                <select
                  value={overrideFlag}
                  onChange={(e) => setOverrideFlag(e.target.value as AuthenticityLevel)}
                  className="w-full px-4 py-2.5 text-xs rounded-xl border border-[var(--border-default)] bg-[var(--bg-card-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--border-focus)]"
                >
                  <option value="low">Low Likelihood (Spontaneous Answer)</option>
                  <option value="medium">Medium Likelihood (Potential Reading)</option>
                  <option value="high">High Likelihood (Script Reading)</option>
                </select>
              </div>

              <div className="space-y-1.5 text-left">
                <label className="block text-xs font-medium text-[var(--text-secondary)]">
                  Administrative Justification Reason
                </label>
                <textarea
                  rows={2}
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="Required for administrative audit log..."
                  className="w-full p-3 text-xs rounded-xl border border-[var(--border-default)] bg-[var(--bg-card-subtle)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--border-focus)]"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsOverrideOpen(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleApplyOverride}
              >
                Confirm & Log Override
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
