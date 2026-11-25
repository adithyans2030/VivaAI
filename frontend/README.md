# VivaIQ Frontend

React 19 single-page app built with [Vite](https://vite.dev), [React Router](https://reactrouter.com) and Tailwind CSS 4.

## Run it

```bash
cp .env.example .env.local   # Windows: copy .env.example .env.local
npm install
npm run dev                  # http://localhost:3000
```

The backend must be running (default `http://localhost:8000`). Port 3000 is fixed because it is the origin the
backend allows in `CORS_ORIGINS`.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload on port 3000 |
| `npm run build` | Type-check, then build the static bundle into `dist/` |
| `npm run preview` | Serve the built `dist/` on port 3000 |
| `npm run lint` | ESLint (TypeScript, React hooks, fast-refresh rules) |
| `npm run type-check` | TypeScript only |

## Configuration

Vite only exposes variables prefixed with `VITE_`, and inlines them **at build time**. Change them, then restart
`npm run dev` or rebuild.

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api/v1` | REST API base |
| `VITE_WS_URL` | `ws://localhost:8000/api/v1/ws` | WebSocket base for the viva room |
| `VITE_DEMO_MODE` | `false` | Shows one-click demo accounts on `/login`. The demo passwords end up in the public bundle, so never enable this on a real deployment |

## Layout

```
index.html              page shell: fonts, title, theme-flash guard
src/main.tsx            route table
src/RootLayout.tsx      navbar + active page
src/pages/              one component per route (pages/teacher/* share TeacherLayout)
src/components/         shared UI (audio orb, mic check, navbar, theme, primitives)
src/lib/                API + WebSocket clients, audio recorder, helpers
```

`@/` is an alias for `src/`.

## Deploying

`docker build` produces an nginx image serving `dist/` on port 3000, with every route falling back to
`index.html` so deep links such as `/teacher/sessions/<id>` work. Pass the `VITE_*` values as `--build-arg`s.
Any other static host works the same way, as long as unknown paths are rewritten to `index.html`.
