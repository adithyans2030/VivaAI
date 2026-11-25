# Security

What VivaIQ does to protect accounts and student data, and the known gaps. Pair with
[privacy-and-retention.md](privacy-and-retention.md).

## Authentication

| Control | Implementation |
|---|---|
| Passwords | bcrypt hashes; minimum 8 characters |
| Tokens | JWT (HS256). Access token 30 min, refresh token 7 days (`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`) |
| Refresh rotation | Each `/auth/refresh` revokes the old refresh token in the `revoked_tokens` table (unique per token id, so concurrent replays cannot both succeed); replaying it returns 401, also after a restart |
| Browser session | httpOnly cookies set by the backend: `vivaiq_access` (path `/api/v1`) and `vivaiq_refresh` (path `/api/v1/auth` only). Page script never sees a token: cookie refreshes return new cookies, not tokens in the body. `SameSite=Lax`; `Secure` in production (`AUTH_COOKIE_*` settings) |
| CSRF | Every cookie-authenticated `POST`/`PUT`/`DELETE` (including cookie refresh and logout) must send `X-VivaIQ-CSRF`. A cross-site page cannot add a custom header without a CORS preflight, which only `CORS_ORIGINS` pass. Requests using a Bearer header or a body refresh token are not cookie-authenticated and need no header |
| API clients | `Authorization: Bearer <access_token>`; `/auth/login` still returns the tokens in its body, and `/auth/refresh` with `{"refresh_token"}` returns new ones |
| Logout | Revokes the refresh token (cookie or body) server-side and clears the cookies; works even if the access token has expired |
| Registration | Public sign-up always creates a **student**; teachers/admins are created only by an admin (`POST /auth/admin/users`) |
| Rate limiting | Login and registration: 10 attempts/min (per IP + email, per IP), counted in the database so the limit holds across restarts and workers |
| WebSocket auth | Single-use tickets only, valid for 30 s, bound to one session, stored in the database and consumed with one atomic update (see [websocket-protocol.md](websocket-protocol.md)). JWTs in the URL and the auth cookies are not accepted on the WebSocket |
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
  delimited section of the grader prompt, never in the instructions, and injection attempts are flagged
  for teacher review. The log records only the turn ID, never the answer text.
- **WebSocket:** per-turn audio buffer capped at 9.6 MB; idle connections are closed after 60 s; unknown
  turn IDs are rejected; errors sent to clients are generic, with details only in the server log.

## Transport & browser

- **CORS:** explicit origins only (`CORS_ORIGINS`); `*` is refused at startup. Credentialed CORS is on
  (the session is a cookie), which is safe only because the origin list is explicit.
- Serve over HTTPS/WSS in any real deployment (terminate TLS at a reverse proxy).
- Tokens are never stored in `localStorage` (only the non-secret profile, `vivaiq_user`, for the navbar).
  An XSS bug could still act as the user while the page is open, but could not steal a token for later.
  The frontend renders no user-supplied HTML; keep it that way.

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
| Refresh rotation has no grace period | If a refresh is cut off by a navigation after the server rotated the token, the browser keeps the revoked cookie and the user must log in again (the client avoids needless rotations to make this rare) | Short reuse window for the previous refresh token if it shows up in practice |
| Logout revokes the refresh token, not the current access token | A stolen access token stays valid until it expires (≤ 30 min) | Short expiry; add an access-token deny-list if needed |
| No account lockout beyond the per-minute rate limit | Slow brute force is possible | Lockout/backoff per account |
| Demo passwords are bundled when `VITE_DEMO_MODE=true` | Fine for a demo machine; never enable on a public deployment | Documented in `frontend/.env.example` |

## Reporting

Report vulnerabilities privately to the maintainers rather than in a public issue.
