/**
 * VivaIQ API Client
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "student" | "teacher" | "admin";
  is_active: boolean;
}

export interface Subject {
  id: string;
  name: string;
  code: string;
  description: string;
  teacher_id: string;
  document_count?: number;
}

export interface DocumentItem {
  id: string;
  subject_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  chunk_count: number;
  ingestion_status: "pending" | "processing" | "completed" | "failed";
  error_message?: string;
}

export interface OverrideResult {
  message: string;
  updated_session_score: number | null;
  updated_session_flag: "low" | "medium" | "high" | "unknown";
}

export interface Turn {
  id: string;
  turn_number: number;
  question_text: string;
  question_type: string;
  topic: string;
  source_references?: Array<{ source?: string; page?: number; excerpt?: string }>;
  prompt_version?: string;
  transcript?: string;
  score_0_10?: number;
  rubric_breakdown?: {
    correctness: number;
    completeness: number;
    clarity: number;
    depth: number;
    missing_points?: string[];
    incorrect_claims?: string[];
  };
  feedback?: string;
  followup_needed?: boolean;
  followup_type?: string;
  authenticity_likelihood: "low" | "medium" | "high" | "unknown";
  authenticity_confidence?: number;
  authenticity_reasons?: string[];
}

export interface VivaSession {
  id: string;
  student_id: string;
  subject_id: string;
  status: "created" | "warmup" | "in_progress" | "completed" | "cancelled";
  recording_consent: boolean;
  total_score?: number;
  overall_authenticity_likelihood: "low" | "medium" | "high" | "unknown";
  overall_authenticity_confidence?: number;
  overall_authenticity_reasons?: string[];
  teacher_notes?: string;
  created_at: string;
  turns?: Turn[];
  student_name?: string;
  subject_name?: string;
  subject_code?: string;
}

/** FastAPI returns `detail` as a string, or as a list of validation errors for 422s. */
function formatErrorDetail(body: { detail?: unknown; message?: unknown }): string | null {
  const { detail, message } = body;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": "))
      .join("; ");
  }
  return typeof message === "string" ? message : null;
}

const USER_CACHE_KEY = "vivaiq_user";

/**
 * Every request carries this header. The session lives in httpOnly cookies the page cannot read;
 * the backend refuses cookie-authenticated writes without the header, which a cross-site page
 * cannot add (CSRF protection).
 */
const BASE_HEADERS: Record<string, string> = { "X-VivaIQ-CSRF": "1" };

function readCachedUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_CACHE_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

function writeCachedUser(user: User | null) {
  try {
    if (user) localStorage.setItem(USER_CACHE_KEY, JSON.stringify(user));
    else localStorage.removeItem(USER_CACHE_KEY);
  } catch {
    // Storage blocked (private mode): the profile is simply fetched again.
  }
}

// Tokens used to live in localStorage. Remove any left behind by an older build.
try {
  localStorage.removeItem("vivaiq_token");
  localStorage.removeItem("vivaiq_refresh");
} catch {
  // Storage unavailable: nothing to clean up.
}

class ApiClient {
  private refreshInFlight: Promise<boolean> | null = null;
  /** When the last successful refresh finished (ms). */
  private lastRefreshAt = 0;

  /** Profile of the signed-in user from the last successful `getMe`. Not a credential. */
  getCachedUser(): User | null {
    return readCachedUser();
  }

  private clearSession() {
    writeCachedUser(null);
  }

  /** Same-origin cookies go with every request; tokens never touch page script. */
  private send(endpoint: string, options: RequestInit = {}): Promise<Response> {
    return fetch(`${API_BASE}${endpoint}`, {
      ...options,
      credentials: "include",
      headers: { ...BASE_HEADERS, ...(options.headers as Record<string, string>) },
    });
  }

  /**
   * Rotate the session using the httpOnly refresh cookie. Concurrent 401s share one attempt, and a
   * request sent before the last successful refresh just retries: rotating again would be wasted, and
   * a rotation cut off by a navigation leaves the browser holding a revoked refresh cookie.
   */
  private refreshSession(requestSentAt: number): Promise<boolean> {
    if (this.refreshInFlight) return this.refreshInFlight;
    if (requestSentAt < this.lastRefreshAt) return Promise.resolve(true);
    this.refreshInFlight = this.send("/auth/refresh", { method: "POST" })
      .then((res) => {
        if (res.ok) this.lastRefreshAt = Date.now();
        return res.ok;
      })
      .catch(() => false)
      .finally(() => {
        this.refreshInFlight = null;
      });
    return this.refreshInFlight;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}, isRetry = false): Promise<T> {
    const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const sentAt = Date.now();
    const response = await this.send(endpoint, { ...options, headers });

    if (response.status === 401) {
      if (!isRetry && (await this.refreshSession(sentAt))) {
        return this.request<T>(endpoint, options, true);
      }
      this.clearSession();
      if (typeof window !== "undefined" && !window.location.pathname.includes("/login")) {
        // Plain module (no router available); a full navigation also resets client state.
        window.location.href = "/login";
      }
      throw new Error("Session expired. Please log in again.");
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(formatErrorDetail(errorData) || `Request failed (${response.status})`);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  // Auth
  /** Signs in; the backend answers with httpOnly session cookies. Token fields in the body are ignored. */
  async login(username: string, password: string): Promise<void> {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);

    const res = await this.send("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(formatErrorDetail(err) || "Invalid email or password");
    }
  }

  /** Revoke the refresh token server-side and clear the session cookies. */
  async logout(): Promise<void> {
    try {
      await this.send("/auth/logout", { method: "POST" });
    } catch {
      // Offline: the cookies expire on their own; forget the cached profile regardless.
    }
    this.clearSession();
  }

  async getMe(): Promise<User> {
    const user = await this.request<User>("/auth/me");
    writeCachedUser(user);
    return user;
  }

  // Subjects
  async listSubjects(): Promise<Subject[]> {
    return this.request<Subject[]>("/subjects");
  }

  async createSubject(data: { name: string; code: string; description: string }): Promise<Subject> {
    return this.request<Subject>("/subjects", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getSubject(id: string): Promise<Subject & { documents: DocumentItem[] }> {
    return this.request<Subject & { documents: DocumentItem[] }>(`/subjects/${id}`);
  }

  // Documents
  async listDocuments(subjectId: string): Promise<DocumentItem[]> {
    return this.request<DocumentItem[]>(`/subjects/${subjectId}/documents`);
  }

  async uploadDocument(subjectId: string, file: File): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append("file", file);
    return this.request<DocumentItem>(`/subjects/${subjectId}/documents`, {
      method: "POST",
      body: formData,
    });
  }

  async deleteDocument(documentId: string): Promise<void> {
    return this.request<void>(`/documents/${documentId}`, {
      method: "DELETE",
    });
  }

  // Sessions
  async createSession(subjectId: string): Promise<VivaSession> {
    return this.request<VivaSession>("/sessions", {
      method: "POST",
      body: JSON.stringify({ subject_id: subjectId }),
    });
  }

  async recordConsent(sessionId: string, consent: boolean): Promise<VivaSession> {
    return this.request<VivaSession>(`/sessions/${sessionId}/consent`, {
      method: "POST",
      body: JSON.stringify({ recording_consent: consent }),
    });
  }

  async listSessions(params: { subject_id?: string; student_id?: string; status_filter?: string } = {}): Promise<VivaSession[]> {
    const query = new URLSearchParams();
    if (params.subject_id) query.append("subject_id", params.subject_id);
    if (params.student_id) query.append("student_id", params.student_id);
    if (params.status_filter) query.append("status_filter", params.status_filter);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return this.request<VivaSession[]>(`/sessions${qs}`);
  }

  async getSession(id: string): Promise<VivaSession> {
    return this.request<VivaSession>(`/sessions/${id}`);
  }

  async getWsTicket(sessionId: string): Promise<string> {
    const data = await this.request<{ ticket: string; expires_in: number }>(`/sessions/${sessionId}/ws-ticket`, {
      method: "POST",
    });
    return data.ticket;
  }

  // Reports & Overrides
  async updateTeacherNotes(sessionId: string, notes: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/reports/sessions/${sessionId}/notes`, {
      method: "POST",
      body: JSON.stringify({ teacher_notes: notes }),
    });
  }

  async overrideScore(
    sessionId: string,
    data: { turn_id?: string; new_score: number; new_authenticity?: string; reason: string }
  ): Promise<OverrideResult> {
    return this.request<OverrideResult>(`/reports/sessions/${sessionId}/override`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  /** Authenticated binary download (the session cookie goes with it). */
  private async fetchBlob(endpoint: string, isRetry = false): Promise<Blob> {
    const sentAt = Date.now();
    const response = await this.send(endpoint);
    if (response.status === 401 && !isRetry && (await this.refreshSession(sentAt))) {
      return this.fetchBlob(endpoint, true);
    }
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(formatErrorDetail(errorData) || `Request failed (${response.status})`);
    }
    return response.blob();
  }

  async getTurnAudio(sessionId: string, turnId: string): Promise<Blob> {
    return this.fetchBlob(`/sessions/${sessionId}/turns/${turnId}/audio`);
  }

  /** Download a session report export ("csv" or "pdf") with the user's credentials. */
  async downloadSessionExport(sessionId: string, format: "csv" | "pdf"): Promise<void> {
    const blob = await this.fetchBlob(`/reports/sessions/${sessionId}/export/${format}`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `viva-session-${sessionId}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  }
}

export const api = new ApiClient();
