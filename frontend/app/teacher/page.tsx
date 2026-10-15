"use client";

import { useEffect, useState } from "react";
import { api, Subject, VivaSession, DocumentItem, Turn } from "@/lib/api";
import {
  LayoutDashboard,
  BookOpen,
  UploadCloud,
  FileText,
  Search,
  Filter,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Download,
  Edit3,
  Trash2,
  Layers,
  ChevronRight,
  TrendingUp,
  UserCheck,
  Volume2,
} from "lucide-react";

export default function TeacherDashboardPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [sessions, setSessions] = useState<VivaSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<VivaSession | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [activeTab, setActiveTab] = useState<"sessions" | "documents" | "analytics">("sessions");

  // Filter state
  const [filterFlag, setFilterFlag] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Override Modal
  const [isOverrideOpen, setIsOverrideOpen] = useState(false);
  const [overrideScore, setOverrideScore] = useState<number>(8.5);
  const [overrideFlag, setOverrideFlag] = useState<string>("low");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [teacherNotes, setTeacherNotes] = useState<string>("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
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
    } catch {
      // Provide demo teacher data for preview
      const demoSubjects: Subject[] = [
        {
          id: "cs301",
          name: "Operating Systems & Concurrency",
          code: "CS301",
          description: "Deadlocks, CPU Scheduling, Virtual Memory",
          teacher_id: "teacher-1",
          document_count: 2,
        },
      ];

      const demoSessions: VivaSession[] = [
        {
          id: "sess-ada",
          student_id: "s-1",
          student_name: "Ada Lovelace",
          subject_id: "cs301",
          subject_name: "Operating Systems",
          subject_code: "CS301",
          status: "completed",
          recording_consent: true,
          total_score: 8.8,
          overall_authenticity_likelihood: "low",
          overall_authenticity_confidence: 0.92,
          overall_authenticity_reasons: [
            "Conversational pause rate matches spontaneous baseline",
            "Synthesized analogies not found in textbook documents",
          ],
          teacher_notes: "Strong conceptual grasp of mutual exclusion and memory barriers.",
          created_at: new Date().toISOString(),
          turns: [
            {
              id: "t-1",
              turn_number: 1,
              question_type: "conceptual",
              topic: "Deadlocks",
              question_text: "What are Coffman's four conditions for deadlock?",
              transcript: "The four conditions are Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait. If any one is broken, deadlock cannot occur.",
              score_0_10: 9.0,
              authenticity_likelihood: "low",
              authenticity_confidence: 0.94,
              authenticity_reasons: [
                "Natural prosodic pitch variability",
                "Spontaneous hesitation at technical terms",
              ],
              feedback: "Accurate enumeration and clear condition explanation.",
            },
            {
              id: "t-2",
              turn_number: 2,
              question_type: "probe",
              topic: "Banker's Algorithm",
              question_text: "In your own words, why is Banker's algorithm impractical in general-purpose operating systems?",
              transcript: "Because it requires processes to state their maximum resource claim upfront, and in modern dynamic systems like Linux, processes don't know their future resource requirements ahead of time.",
              score_0_10: 8.6,
              authenticity_likelihood: "low",
              authenticity_confidence: 0.9,
              authenticity_reasons: ["Zero verbatim overlap with slides", "Natural sentence restarts"],
              feedback: "Insightful practical consideration cited regarding Linux dynamics.",
            },
          ],
        },
        {
          id: "sess-bob",
          student_id: "s-2",
          student_name: "Robert Smith",
          subject_id: "cs301",
          subject_name: "Operating Systems",
          subject_code: "CS301",
          status: "completed",
          recording_consent: true,
          total_score: 6.2,
          overall_authenticity_likelihood: "medium",
          overall_authenticity_confidence: 0.74,
          overall_authenticity_reasons: [
            "High 4-gram verbatim overlap with textbook section 4.2",
            "Atypical rhythmic pacing with prolonged reading pauses at line breaks",
          ],
          created_at: new Date(Date.now() - 86400000).toISOString(),
          turns: [],
        },
      ];

      setSubjects(demoSubjects);
      setSessions(demoSessions);
      setSelectedSession(demoSessions[0]);
    }
  };

  // Upload Document Handler
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || subjects.length === 0) return;

    try {
      await api.uploadDocument(subjects[0].id, file);
      const updatedDocs = await api.listDocuments(subjects[0].id);
      setDocuments(updatedDocs);
    } catch {
      // Mock add
      setDocuments((prev) => [
        ...prev,
        {
          id: `doc-${Date.now()}`,
          subject_id: subjects[0].id,
          filename: file.name,
          file_type: file.name.split(".").pop() || "txt",
          file_size_bytes: file.size,
          chunk_count: 14,
          ingestion_status: "completed",
        },
      ]);
    }
  };

  // Submit Override
  const handleApplyOverride = async () => {
    if (!selectedSession) return;
    try {
      await api.overrideScore(selectedSession.id, {
        new_score: overrideScore,
        new_authenticity: overrideFlag,
        reason: overrideReason || "Teacher manual review",
      });
    } catch {
      // Update local state
      setSelectedSession((prev) =>
        prev
          ? {
              ...prev,
              total_score: overrideScore,
              overall_authenticity_likelihood: overrideFlag as any,
            }
          : null
      );
    }
    setIsOverrideOpen(false);
  };

  // Save Teacher Notes
  const handleSaveNotes = async () => {
    if (!selectedSession) return;
    try {
      await api.updateTeacherNotes(selectedSession.id, teacherNotes);
    } catch {
      setSelectedSession((prev) => (prev ? { ...prev, teacher_notes: teacherNotes } : null));
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      {/* Dashboard Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Teacher Portal
          </span>
          <h1 className="text-3xl font-bold text-white tracking-tight mt-1">Examiner Assessment Dashboard</h1>
          <p className="text-sm text-slate-400">
            Review oral examination recordings, rubric evaluations, and advisory authenticity findings.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1.5 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab("sessions")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === "sessions" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Viva Sessions ({sessions.length})
          </button>
          <button
            onClick={() => setActiveTab("documents")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === "documents" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Course Material (RAG)
          </button>
          <button
            onClick={() => setActiveTab("analytics")}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors ${
              activeTab === "analytics" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Class Analytics
          </button>
        </div>
      </div>

      {/* SESSIONS TAB */}
      {activeTab === "sessions" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left: Sessions List & Filters */}
          <div className="lg:col-span-5 space-y-4">
            <div className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-3">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search candidate by name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
                />
              </div>

              {/* Authenticity Filter */}
              <div className="flex items-center gap-1.5 pt-2 border-t border-slate-800">
                <Filter className="w-3.5 h-3.5 text-slate-500" />
                <span className="text-[11px] text-slate-400 font-medium">Authenticity:</span>
                {["all", "low", "medium", "high"].map((level) => (
                  <button
                    key={level}
                    onClick={() => setFilterFlag(level)}
                    className={`px-2 py-0.5 rounded text-[11px] font-semibold capitalize transition-colors ${
                      filterFlag === level
                        ? "bg-slate-700 text-white"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>

            {/* Candidate Session Cards */}
            <div className="space-y-3">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => {
                    setSelectedSession(s);
                    setTeacherNotes(s.teacher_notes || "");
                  }}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                    selectedSession?.id === s.id
                      ? "bg-indigo-950/40 border-indigo-500 shadow-md"
                      : "glass-panel border-slate-800 hover:border-slate-700 hover:bg-slate-900/60"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-white">{s.student_name || "Candidate"}</h4>
                      <div className="text-xs text-slate-400">{s.subject_name || "Operating Systems"}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-emerald-400">
                        {s.total_score ? `${s.total_score}/10` : "Pending"}
                      </div>
                      <span
                        className={`inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          s.overall_authenticity_likelihood === "low"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : s.overall_authenticity_likelihood === "medium"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                        }`}
                      >
                        {s.overall_authenticity_likelihood} Flag
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Detailed Session Inspector */}
          {selectedSession && (
            <div className="lg:col-span-7 space-y-6">
              {/* Top Overview Card */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-white">{selectedSession.student_name}</h2>
                    <p className="text-xs text-slate-400">{selectedSession.subject_name} • Oral Viva Voce</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setIsOverrideOpen(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      Override Grade / Flag
                    </button>
                    <a
                      href={api.getExportCsvUrl(selectedSession.id)}
                      download
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Export CSV
                    </a>
                  </div>
                </div>

                {/* Score & Authenticity Highlights */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
                    <div className="text-[11px] text-slate-400 uppercase font-semibold">Overall Rubric Score</div>
                    <div className="text-2xl font-black text-indigo-400 mt-1">
                      {selectedSession.total_score}/10
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800">
                    <div className="text-[11px] text-slate-400 uppercase font-semibold">Advisory Authenticity</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-lg font-bold capitalize text-emerald-400">
                        {selectedSession.overall_authenticity_likelihood} Likelihood of Reading
                      </span>
                    </div>
                  </div>
                </div>

                {/* Authenticity Explainable Reasons (Section 7.4) */}
                {selectedSession.overall_authenticity_reasons && (
                  <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                    <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <ShieldAlert className="w-4 h-4 text-amber-400" />
                      Advisory Acoustic & Textual Evidence:
                    </div>
                    <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
                      {selectedSession.overall_authenticity_reasons.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Turns and Audio Review */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
                <h3 className="text-base font-bold text-white">Question Turns & Spoken Transcripts</h3>

                <div className="space-y-4">
                  {selectedSession.turns?.map((turn) => (
                    <div key={turn.id} className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-indigo-300">
                          Question #{turn.turn_number}: {turn.topic} ({turn.question_type})
                        </span>
                        <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                          {turn.score_0_10}/10
                        </span>
                      </div>

                      <p className="text-xs font-medium text-slate-200">"{turn.question_text}"</p>

                      <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs text-slate-300 italic">
                        <span className="text-[10px] text-slate-500 uppercase not-italic block mb-1">Transcript:</span>
                        "{turn.transcript}"
                      </div>

                      <div className="text-[11px] text-slate-400 flex items-center justify-between border-t border-slate-800/80 pt-2">
                        <span>Feedback: {turn.feedback}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Teacher Notes & Audit Trail */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-3">
                <h3 className="text-sm font-bold text-white">Teacher Evaluation Notes</h3>
                <textarea
                  rows={3}
                  value={teacherNotes}
                  onChange={(e) => setTeacherNotes(e.target.value)}
                  placeholder="Add advisory notes, student recommendations, or oral viva observations..."
                  className="w-full p-3 rounded-xl bg-slate-900 border border-slate-700 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
                <div className="flex justify-end">
                  <button
                    onClick={handleSaveNotes}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-colors"
                  >
                    Save Notes
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* DOCUMENTS TAB (RAG INGESTION) */}
      {activeTab === "documents" && (
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white">Course Materials & Ingestion Pipeline</h2>
              <p className="text-xs text-slate-400">
                Uploaded PDF, DOCX, TXT, and Markdown files are chunked, embedded, and stored for grounded questioning.
              </p>
            </div>

            <label className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-500/25 cursor-pointer transition-all">
              <UploadCloud className="w-4 h-4" />
              Upload Subject Material
              <input type="file" onChange={handleUpload} className="hidden" accept=".pdf,.docx,.txt,.md" />
            </label>
          </div>

          <div className="space-y-3">
            {documents.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">
                No course material uploaded yet. Upload lecture notes, textbook chapters, or syllabi.
              </div>
            ) : (
              documents.map((doc) => (
                <div key={doc.id} className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-indigo-400" />
                    <div>
                      <div className="text-sm font-semibold text-slate-200">{doc.filename}</div>
                      <div className="text-[11px] text-slate-400">
                        {doc.chunk_count} semantic chunks • {(doc.file_size_bytes / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>

                  <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 capitalize">
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
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
          <h2 className="text-lg font-bold text-white">Class-Level Performance & Topic Mastery</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
              <div className="text-xs text-slate-400">Class Average Score</div>
              <div className="text-3xl font-extrabold text-indigo-400 mt-2">7.8 / 10</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
              <div className="text-xs text-slate-400">Total Completed Vivas</div>
              <div className="text-3xl font-extrabold text-emerald-400 mt-2">{sessions.length}</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
              <div className="text-xs text-slate-400">Advisory Authenticity Flags</div>
              <div className="text-3xl font-extrabold text-amber-400 mt-2">1 Review Recommended</div>
            </div>
          </div>
        </div>
      )}

      {/* Override Grade / Flag Modal */}
      {isOverrideOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel bg-slate-900 rounded-2xl p-6 border border-slate-700 shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-white">Override Examination Grade</h3>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Revised Score (0 - 10)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="10"
                value={overrideScore}
                onChange={(e) => setOverrideScore(parseFloat(e.target.value))}
                className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Revised Authenticity Flag</label>
              <select
                value={overrideFlag}
                onChange={(e) => setOverrideFlag(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white"
              >
                <option value="low">Low (Spontaneous Answer)</option>
                <option value="medium">Medium (Potential Script Reading)</option>
                <option value="high">High (Extensive Verbatim Reading)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Audit Justification Reason</label>
              <textarea
                rows={2}
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Required for administrative audit log..."
                className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setIsOverrideOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleApplyOverride}
                className="px-5 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 shadow-md"
              >
                Confirm & Log Override
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
