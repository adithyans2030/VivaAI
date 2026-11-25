import type { VivaSession } from "@/lib/api";
import { isFinished } from "@/lib/teacher";

const pill = "inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider border";
const tone = {
  neutral: "bg-[var(--bg-card-subtle)] text-[var(--text-muted)] border-[var(--border-default)]",
  good: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
  bad: "bg-[var(--error-bg)] text-[var(--error-text)] border-[var(--error-border)]",
  info: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
};

export function StatusBadge({ status }: { status: VivaSession["status"] }) {
  const map: Record<VivaSession["status"], [string, keyof typeof tone]> = {
    completed: ["Completed", "good"],
    in_progress: ["In progress", "info"],
    warmup: ["In progress", "info"],
    created: ["Not started", "neutral"],
    cancelled: ["Cancelled", "neutral"],
  };
  const [label, t] = map[status] ?? [status, "neutral"];
  return <span className={`${pill} ${tone[t]}`}>{label}</span>;
}

/** Advisory flag. Unfinished or unassessed sessions are shown neutrally, never as a red alert. */
export function FlagBadge({ session }: { session: Pick<VivaSession, "status" | "overall_authenticity_likelihood"> }) {
  const level = session.overall_authenticity_likelihood;
  if (!isFinished(session) || level === "unknown" || !level) {
    return <span className={`${pill} ${tone.neutral}`}>Not assessed</span>;
  }
  const t = level === "low" ? "good" : level === "medium" ? "warn" : "bad";
  return <span className={`${pill} ${tone[t]}`}>{level} flag</span>;
}

export function ErrorBanner({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div
      role="alert"
      className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-400 flex items-center justify-between gap-3 text-xs"
    >
      <span>{message}</span>
      {onDismiss && (
        <button onClick={onDismiss} aria-label="Dismiss" className="font-bold hover:opacity-80 cursor-pointer">
          ✕
        </button>
      )}
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-5 border-b border-[var(--border-default)]">
      <div>
        <h1 className="font-editorial text-2xl sm:text-3xl font-normal tracking-tight text-[var(--text-primary)]">{title}</h1>
        {description && <p className="text-sm text-[var(--text-secondary)] mt-1 max-w-2xl">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
}

export const card = "rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs";
export const fieldClass =
  "w-full px-3 py-2 text-sm rounded-xl border border-[var(--border-default)] bg-[var(--bg-card-subtle)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--border-focus)]";
