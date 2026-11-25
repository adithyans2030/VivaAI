import { Link } from "react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, DocumentItem, Subject } from "@/lib/api";
import Button from "@/components/ui/Button";
import { ErrorBanner, PageHeader, card, fieldClass } from "@/components/teacher/shared";
import { errorText } from "@/lib/teacher";
import { FileText, Trash2, UploadCloud } from "lucide-react";

const ACCEPT = ".pdf,.docx,.txt,.md";
const IN_FLIGHT: DocumentItem["ingestion_status"][] = ["pending", "processing"];

const statusTone: Record<DocumentItem["ingestion_status"], string> = {
  completed: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  pending: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
  processing: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
  failed: "bg-[var(--error-bg)] text-[var(--error-text)] border-[var(--error-border)]",
};
const statusLabel: Record<DocumentItem["ingestion_status"], string> = {
  completed: "Ready",
  pending: "Queued",
  processing: "Processing…",
  failed: "Failed",
};

export default function CourseMaterialPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [subjectId, setSubjectId] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listSubjects()
      .then((list) => {
        if (cancelled) return;
        setSubjects(list);
        // /teacher/materials?subject=<id> (linked from the Subjects page) preselects that subject.
        const wanted = new URLSearchParams(window.location.search).get("subject");
        setSubjectId(list.find((s) => s.id === wanted)?.id ?? list[0]?.id ?? "");
      })
      .catch((err) => !cancelled && setError(errorText(err, "Could not load your subjects.")));
    return () => {
      cancelled = true;
    };
  }, []);

  const loadDocuments = useCallback(async (id: string, quiet = false) => {
    if (!id) return;
    if (!quiet) setIsLoadingDocs(true);
    try {
      setDocuments(await api.listDocuments(id));
    } catch (err) {
      setError(errorText(err, "Could not load documents."));
    } finally {
      if (!quiet) setIsLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void loadDocuments(subjectId), 0);
    return () => clearTimeout(timer);
  }, [subjectId, loadDocuments]);

  // While anything is still being chunked/embedded, refresh so the status updates by itself.
  const hasInFlight = documents.some((d) => IN_FLIGHT.includes(d.ingestion_status));
  useEffect(() => {
    if (!hasInFlight) return;
    const id = setInterval(() => void loadDocuments(subjectId, true), 3000);
    return () => clearInterval(id);
  }, [hasInFlight, subjectId, loadDocuments]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file || !subjectId) return;
    setError(null);
    setIsUploading(true);
    try {
      await api.uploadDocument(subjectId, file);
      await loadDocuments(subjectId, true);
    } catch (err) {
      setError(`Upload failed: ${errorText(err, "Accepted types are PDF, DOCX, TXT and MD up to 25 MB.")}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (doc: DocumentItem) => {
    if (!window.confirm(`Delete "${doc.filename}"? Questions will no longer be drawn from it.`)) return;
    setError(null);
    try {
      await api.deleteDocument(doc.id);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (err) {
      setError(`Delete failed: ${errorText(err)}`);
    }
  };

  const subject = subjects.find((s) => s.id === subjectId);

  return (
    <>
      <PageHeader
        title="Course Material"
        description="The examiner asks questions only from the notes, slides and textbook chapters you upload for each subject."
      />

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {subjects.length === 0 && !error ? (
        <div className={`${card} p-10 text-center space-y-3`}>
          <p className="text-sm text-[var(--text-muted)]">You don&rsquo;t have any subjects yet.</p>
          <Link to="/teacher/subjects" className="text-sm font-semibold text-[var(--accent-primary)] hover:underline">
            Create your first subject →
          </Link>
        </div>
      ) : (
        <section className={`${card} p-5 sm:p-6 space-y-5`}>
          <div className="flex flex-col sm:flex-row sm:items-end gap-3">
            <label className="flex-1 space-y-1.5">
              <span className="text-xs font-medium text-[var(--text-secondary)]">Subject</span>
              <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className={fieldClass}>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} · {s.name}
                  </option>
                ))}
              </select>
            </label>
            <input ref={fileInput} type="file" accept={ACCEPT} onChange={handleUpload} className="hidden" />
            <Button className="gap-1.5" onClick={() => fileInput.current?.click()} isLoading={isUploading} disabled={!subjectId}>
              <UploadCloud className="w-4 h-4" />
              Upload to {subject?.code ?? "subject"}
            </Button>
          </div>
          <p className="text-[11px] text-[var(--text-muted)] -mt-2">PDF, DOCX, TXT or Markdown, up to 25 MB each.</p>

          {isLoadingDocs ? (
            <div className="h-20 rounded-xl bg-[var(--bg-card-subtle)] animate-pulse" role="status" aria-label="Loading documents" />
          ) : documents.length === 0 ? (
            <div className="text-center py-10 text-sm text-[var(--text-muted)] border border-dashed border-[var(--border-default)] rounded-xl">
              No material for this subject yet. Upload lecture notes or a textbook chapter to get started.
            </div>
          ) : (
            <ul className="space-y-2">
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className="p-3.5 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] flex items-center gap-3"
                >
                  <div className="w-9 h-9 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] flex items-center justify-center text-[var(--accent-primary)] shrink-0">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-[var(--text-primary)] truncate">{doc.filename}</div>
                    <div className="text-[11px] text-[var(--text-muted)]">
                      {doc.chunk_count} sections · {(doc.file_size_bytes / 1024).toFixed(0)} KB
                      {doc.ingestion_status === "failed" && doc.error_message && (
                        <span className="text-[var(--error-text)]"> · {doc.error_message}</span>
                      )}
                    </div>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider border shrink-0 ${statusTone[doc.ingestion_status]}`}
                  >
                    {statusLabel[doc.ingestion_status]}
                  </span>
                  <button
                    onClick={() => void handleDelete(doc)}
                    aria-label={`Delete ${doc.filename}`}
                    className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--error-text)] hover:bg-[var(--error-bg)] cursor-pointer shrink-0"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}
