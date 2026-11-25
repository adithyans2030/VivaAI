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

class ApiClient {
  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("vivaiq_token");
  }

  private refreshInFlight: Promise<boolean> | null = null;

  setToken(token: string, refreshToken?: string) {
    if (typeof window !== "undefined") {
      localStorage.setItem("vivaiq_token", token);
      if (refreshToken) localStorage.setItem("vivaiq_refresh", refreshToken);
    }
  }

  clearToken() {
    if (typeof window !== "undefined") {
      localStorage.removeItem("vivaiq_token");
      localStorage.removeItem("vivaiq_refresh");
      localStorage.removeItem("vivaiq_user");
    }
  }

  /** Exchange the stored refresh token (rotated server-side). Concurrent 401s share one attempt. */
  private refreshAccessToken(): Promise<boolean> {
    if (this.refreshInFlight) return this.refreshInFlight;
    const refreshToken = typeof window !== "undefined" ? localStorage.getItem("vivaiq_refresh") : null;
    if (!refreshToken) return Promise.resolve(false);

    this.refreshInFlight = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const data: { access_token: string; refresh_token: string } = await res.json();
        this.setToken(data.access_token, data.refresh_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        this.refreshInFlight = null;
      });
    return this.refreshInFlight;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}, isRetry = false): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      if (!isRetry && (await this.refreshAccessToken())) {
        return this.request<T>(endpoint, options, true);
      }
      this.clearToken();
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
  async login(username: string, password: string):Promise<{ access_token: string; refresh_token: string }> {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);

    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Invalid email or password");
    }

    const data = await res.json();
    this.setToken(data.access_token, data.refresh_token);
    return data;
  }

  /** Revoke the refresh token server-side, then forget local credentials. */
  async logout(): Promise<void> {
    const refreshToken = typeof window !== "undefined" ? localStorage.getItem("vivaiq_refresh") : null;
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(this.getToken() ? { Authorization: `Bearer ${this.getToken()}` } : {}),
        },
        body: refreshToken ? JSON.stringify({ refresh_token: refreshToken }) : undefined,
      });
    } catch {
      // Offline logout still clears local credentials.
    }
    this.clearToken();
  }

  async getMe(): Promise<User> {
    const user = await this.request<User>("/auth/me");
    if (typeof window !== "undefined") {
      localStorage.setItem("vivaiq_user", JSON.stringify(user));
    }
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

  /** Authenticated binary download (plain links/<audio src> cannot send the bearer header). */
  private async fetchBlob(endpoint: string, isRetry = false): Promise<Blob> {
    const token = this.getToken();
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (response.status === 401 && !isRetry && (await this.refreshAccessToken())) {
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
