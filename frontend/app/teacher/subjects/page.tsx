"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Subject } from "@/lib/api";
import Button from "@/components/ui/Button";
import { ErrorBanner, PageHeader, card, errorText, fieldClass } from "@/components/teacher/shared";
import { FolderOpen, Plus } from "lucide-react";

export default function SubjectsPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .listSubjects()
      .then((list) => {
        if (cancelled) return;
        setSubjects(list);
        if (list.length === 0) setShowForm(true);
      })
      .catch((err) => !cancelled && setError(errorText(err, "Could not load subjects.")))
      .finally(() => !cancelled && setIsLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const canSave = name.trim().length >= 2 && code.trim().length >= 2;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSave) return;
    setIsSaving(true);
    setError(null);
    try {
      const created = await api.createSubject({
        name: name.trim(),
        code: code.trim().toUpperCase(),
        description: description.trim(),
      });
      setSubjects((prev) => [...prev, created]);
      setName("");
      setCode("");
      setDescription("");
      setShowForm(false);
    } catch (err) {
      setError(`Could not create subject: ${errorText(err)}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Subjects"
        description="Each subject has its own course material and its own vivas. Students choose a subject before they start."
        actions={
          !showForm && (
            <Button className="gap-1.5" size="sm" onClick={() => setShowForm(true)}>
              <Plus className="w-3.5 h-3.5" />
              New subject
            </Button>
          )
        }
      />

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {showForm && (
        <form onSubmit={handleCreate} className={`${card} p-5 sm:p-6 space-y-4`}>
          <h2 className="font-editorial text-lg text-[var(--text-primary)]">New subject</h2>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_180px] gap-3">
            <label className="space-y-1.5">
              <span className="text-xs font-medium text-[var(--text-secondary)]">Name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Operating Systems" className={fieldClass} />
            </label>
            <label className="space-y-1.5">
              <span className="text-xs font-medium text-[var(--text-secondary)]">Code</span>
              <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS301" className={`${fieldClass} uppercase`} />
            </label>
          </div>
          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-[var(--text-secondary)]">Description (shown to students)</span>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Processes, scheduling, memory management and concurrency."
              className={fieldClass}
            />
          </label>
          <div className="flex justify-end gap-2">
            {subjects.length > 0 && (
              <Button className="gap-1.5" type="button" variant="ghost" size="sm" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            )}
            <Button className="gap-1.5" type="submit" size="sm" isLoading={isSaving} disabled={!canSave}>
              Create subject
            </Button>
          </div>
        </form>
      )}

      {isLoading ? (
        <div className={`${card} h-24 animate-pulse`} role="status" aria-label="Loading subjects" />
      ) : (
        subjects.length > 0 && (
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {subjects.map((s) => (
              <li key={s.id} className={`${card} p-5 space-y-3`}>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--accent-primary)] font-mono">{s.code}</div>
                <h3 className="font-editorial text-xl text-[var(--text-primary)]">{s.name}</h3>
                {s.description && <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{s.description}</p>}
                <div className="pt-3 border-t border-[var(--border-default)] flex items-center justify-between text-xs">
                  <span className="text-[var(--text-muted)]">
                    {s.document_count ?? 0} document{s.document_count === 1 ? "" : "s"}
                  </span>
                  <Link
                    href={`/teacher/materials?subject=${s.id}`}
                    className="inline-flex items-center gap-1.5 font-semibold text-[var(--accent-primary)] hover:underline"
                  >
                    <FolderOpen className="w-3.5 h-3.5" />
                    Manage material
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )
      )}
    </>
  );
}
