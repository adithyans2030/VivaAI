# Security

What VivaIQ does to protect accounts and student data, and the known gaps. Pair with
[privacy-and-retention.md](privacy-and-retention.md).

## Authentication

| Control | Implementation |
|---|---|
| Passwords | bcrypt hashes; minimum 8 characters |
| Tokens | JWT (HS256). Access token 30 min, refresh token 7 days (`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`) |
| Refresh rotation | Each `/auth/refresh` revokes the old refresh token in the `revoked_tokens` table (unique per token id, so concurrent replays cannot both succeed); replaying it returns 401, also after a restart |
| Logout | Revokes the refresh token server-side, clears local credentials |
| Registration | Public sign-up always creates a **student**; teachers/admins are created only by an admin (`POST /auth/admin/users`) |
| Rate limiting | Login and registration: 10 attempts/min (per IP + email, per IP), counted in the database so the limit holds across restarts and workers |
| WebSocket auth | Single-use tickets valid for 30 s, bound to one session, stored in the database and consumed with one atomic update (see [websocket-protocol.md](websocket-protocol.md)) |
| `SECRET_KEY` | Required in production. Placeholder or empty values are refused at startup; in development a random key is generated per restart (which logs everyone out) |

## Authorization

- Role checks via `require_role` (admins pass every check).
- **Session ownership** (`ensure_session_access`): students reach only their own sessions; teachers only
  sessions in subjects they own. Applied to session details, state, reports, notes, overrides, CSV export,
  audio and WebSocket tickets, and as a filter on `GET /sessions`.
- **Subject ownership** (`ensure_subject_owner`): only the owning teacher can edit or delete a subject or
  upload or delete its documents.
- Teacher overrides require a reason and are written to the audit log with before/after values.

## Input handling

- **Uploads:** extension allow-list (PDF, DOCX, TXT, MD), 25 MB limit, magic-byte check of the content,
  sanitised filenames, stored under generated names.
- **Prompt injection:** the student's spoken answer is treated as untrusted data. It is placed in a
  delimited section of the grader prompt, never in the instructions, and injection attempts are flagged.
- **WebSocket:** per-turn audio buffer capped at 9.6 MB; idle connections are closed after 60 s; unknown
  turn IDs are rejected; errors sent to clients are generic, with details only in the server log.

## Transport & browser

- **CORS:** explicit origins only (`CORS_ORIGINS`); `*` is refused at startup. Credentialed CORS is off
  because auth uses bearer headers, not cookies.
- Serve over HTTPS/WSS in any real deployment (terminate TLS at a reverse proxy).
- Tokens are kept in `localStorage`. This is simple, but any XSS would expose them. The frontend renders
  no user-supplied HTML; keep it that way, and consider httpOnly cookies (see ROADMAP).

## Third-party components

- **ChromaDB** (vector store) is used **embedded** inside the backend process; it opens no port. Its open
  advisories (CVE-2026-45829, -45830, -45831, -45833; no fixed release yet) all concern Chroma's HTTP server
  API and RBAC provider, which VivaIQ does not run. Do not deploy a standalone `chroma run` server for VivaIQ.
- **faster-whisper** is pinned with PyAV 15.x (`requirements-ml.txt`); newer PyAV breaks its audio decoder.

## Secrets

- Only via environment variables (`.env` is git-ignored); `.env.example` holds placeholders.
- Gemini's API key is sent in the `x-goog-api-key` header, so it never appears in request URLs or logs.
- The uvicorn access log is set to WARNING, so request URLs are not logged.
- `pre-commit` runs `detect-private-key`; CI runs `pip-audit` and `npm audit`.

## Production configuration rules (enforced at startup)

- `ENVIRONMENT=production` requires a real `SECRET_KEY` and refuses `DEMO_MODE=true`.
- Mock STT/LLM providers are refused unless `DEMO_MODE=true` or `ENVIRONMENT=testing`.

## Known gaps

| Gap | Impact | Plan |
|---|---|---|
| WebSocket still accepts `?token=<access JWT>` as a fallback | Tokens in URLs can leak via proxy logs | Remove once tests use tickets |
| Tokens in `localStorage` | Exposed if an XSS bug is ever introduced | httpOnly cookie session (ROADMAP) |
| Logout revokes the refresh token, not the current access token | A stolen access token stays valid until it expires (≤ 30 min) | Short expiry; add an access-token deny-list if needed |
| No account lockout beyond the per-minute rate limit | Slow brute force is possible | Lockout/backoff per account |
| Demo passwords are bundled when `VITE_DEMO_MODE=true` | Fine for a demo machine; never enable on a public deployment | Documented in `frontend/.env.example` |

## Reporting

Report vulnerabilities privately to the maintainers rather than in a public issue.
