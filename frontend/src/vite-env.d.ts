/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend REST base, e.g. http://localhost:8000/api/v1 */
  readonly VITE_API_URL?: string;
  /** Backend WebSocket base, e.g. ws://localhost:8000/api/v1/ws */
  readonly VITE_WS_URL?: string;
  /** "true" shows one-click demo accounts on /login (never in real deployments). */
  readonly VITE_DEMO_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
