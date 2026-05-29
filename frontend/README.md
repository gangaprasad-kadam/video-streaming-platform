# VidStream — Frontend

React 18 + Vite SPA for the VidStream distributed video streaming platform.

## Stack

| Tool | Purpose |
|------|---------|
| React 18 + Vite | SPA framework + dev server |
| React Router v6 | Client-side routing |
| Axios | HTTP client (`withCredentials: true`) |
| hls.js | HLS video playback |
| Recharts | Heatmap bar chart |
| Vitest + Testing Library | Unit tests |

## Run (Development)

```bash
npm install
npm run dev        # http://localhost:5173  — proxies /auth, /videos, etc. to :80
```

Backend must be running on port 80 (`cd ../backend && ./start.sh`).

## Run (Docker)

```bash
# Copy and configure
cp .env.example .env
# Edit BACKEND_URL=http://localhost  (or your backend host)

docker compose up --build   # http://localhost:3000
```

## Tests

```bash
npm test           # Vitest watch mode
npm run test:run   # single CI run (55 tests, all passing)
npm run test:coverage
```

## Build

```bash
npm run build      # outputs to dist/
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://localhost` | Backend API base URL (Docker mode only — substituted into nginx.conf.template at container start) |

In dev mode, the Vite proxy handles all API routing — no env var needed.

## Project Structure

```
src/
├── api/          — Axios client + per-service modules (auth, videos, stream, …)
├── context/      — AuthContext (login / logout / register / session rehydrate)
├── hooks/        — useTheme, useVideoStatus, useInteractionTracker, useHeatmapSSE
├── components/   — Navbar, HlsPlayer, VideoCard, SummaryPanel, HeatmapChart, …
├── pages/        — Login, Register, Home, Browse, Player, Upload, Dashboard
└── styles/       — global.css (CSS custom properties, dark/light theme tokens)
```

## Key API Contracts

- `POST /auth/login` returns `{message}` only — profile fetched separately via `GET /users/me`
- `POST /auth/register` expects `username` (not `name`)
- `GET /videos` returns `PagedResponse` `{data, total, page, page_size}` — supports `?q=` title search
- `GET /trending` returns `{videos: [...], total}` after envelope unwrap
- `POST /events/interaction` expects camelCase `{userId, videoId, action, videoTs}`
- `GET /heatmap/{id}/stream` — SSE endpoint; frontend normalises `bucket→segment_id`, `score→count`
