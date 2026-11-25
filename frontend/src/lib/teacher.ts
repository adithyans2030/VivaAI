/** Pure helpers shared by the teacher pages. */
import type { VivaSession } from "@/lib/api";

export const errorText = (err: unknown, fallback = "Server error") => (err instanceof Error && err.message) || fallback;

export const isFinished = (s: Pick<VivaSession, "status">) => s.status === "completed";

/** Completed sessions with a medium/high advisory flag are the ones worth a teacher's look. */
export const needsReview = (s: VivaSession) =>
  isFinished(s) && (s.overall_authenticity_likelihood === "medium" || s.overall_authenticity_likelihood === "high");

export const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

export const formatScore = (score: number | null | undefined) => (score != null ? `${score}/10` : "—");
