# 🖥️ Phase 9 — Frontend Build Plan ✅ COMPLETE
## Distributed Video Streaming Platform — React 18 + Vite

**Location:** `project/frontend/`  
**Stack:** React 18 · Vite · React Router v6 · Axios · hls.js · Recharts · Vitest + Testing Library  
**Status:** ✅ All modules built, all 55 tests passing, production build verified.

---

## 📐 Final Folder Structure

```
frontend/
├── Dockerfile
├── docker-compose.yml             ← standalone frontend on port 3000
├── nginx.conf.template            ← envsubst template; ${BACKEND_URL} substitution
├── vite.config.js
├── package.json
├── index.html
├── .env.example               ← BACKEND_URL=http://localhost  (Docker mode)
├── src/
│   ├── main.jsx               ← React root, Router, QueryClientProvider
│   ├── App.jsx                ← Route definitions
│   ├── index.css              ← Global styles / Tailwind base
│   │
│   ├── api/                   ← Axios client + per-service modules
│   │   ├── client.js          ← Axios instance (baseURL, withCredentials, interceptors)
│   │   ├── auth.js            ← register, login, logout, getMe
│   │   ├── videos.js          ← upload, getVideo, listVideos, getStatus, updateVideo
│   │   ├── stream.js          ← getManifestUrl (returns URL string for hls.js)
│   │   ├── summary.js         ← getSummary
│   │   ├── trending.js        ← getTrending, getRecommendations
│   │   ├── events.js          ← postInteraction
│   │   └── heatmap.js         ← getHeatmap, getLiveHeatmap, getHighlights
│   │
│   ├── context/
│   │   └── AuthContext.jsx    ← user state, login/logout actions, useAuth hook
│   │
│   ├── hooks/                 ← custom React hooks
│   │   ├── useVideoStatus.js  ← polls GET /videos/:id/status until ready/failed
│   │   ├── useHeatmapSSE.js   ← EventSource → live heatmap data
│   │   └── useInteractionTracker.js ← batches play/pause/seek/rewind, flushes every 3s
│   │
│   ├── components/            ← reusable UI building blocks
│   │   ├── Navbar.jsx
│   │   ├── ProtectedRoute.jsx ← redirects to /login if not authenticated
│   │   ├── VideoCard.jsx      ← thumbnail + title + duration card
│   │   ├── VideoGrid.jsx      ← responsive grid of VideoCards
│   │   ├── HlsPlayer.jsx      ← hls.js wrapper, fires interaction events
│   │   ├── SummaryPanel.jsx   ← transcript, summary, key moments list
│   │   ├── HeatmapChart.jsx   ← Recharts BarChart for heatmap segments
│   │   └── UploadProgressBar.jsx
│   │
│   └── pages/
│       ├── LoginPage.jsx
│       ├── RegisterPage.jsx
│       ├── HomePage.jsx       ← trending video grid + recommendations
│       ├── BrowsePage.jsx     ← all videos, search/filter
│       ├── PlayerPage.jsx     ← HLS player + summary panel + heatmap overlay
│       ├── UploadPage.jsx     ← file picker + metadata form + status polling
│       └── DashboardPage.jsx  ← creator's live heatmap + video list
│
└── tests/
    ├── setup.js               ← @testing-library/jest-dom matchers
    ├── api/
    │   ├── client.test.js
    │   ├── auth.test.js
    │   └── videos.test.js
    ├── context/
    │   └── AuthContext.test.jsx
    ├── hooks/
    │   ├── useVideoStatus.test.js
    │   ├── useHeatmapSSE.test.js
    │   └── useInteractionTracker.test.js
    └── components/
        ├── Navbar.test.jsx
        ├── ProtectedRoute.test.jsx
        ├── VideoCard.test.jsx
        ├── HlsPlayer.test.jsx
        ├── SummaryPanel.test.jsx
        └── HeatmapChart.test.jsx
```

---

## 🗂️ Build Modules (in order)

| # | Module | Depends On | Status |
|---|--------|-----------|--------|
| M1 | Project scaffold + Axios client | — | 🔲 |
| M2 | Auth Context + Login/Register pages | M1 | 🔲 |
| M3 | ProtectedRoute + Navbar + routing shell | M2 | 🔲 |
| M4 | Video list pages (Home, Browse) | M3 | 🔲 |
| M5 | HLS Player + interaction tracker | M3 | 🔲 |
| M6 | Upload page + status polling hook | M3 | 🔲 |
| M7 | Summary panel | M5 | 🔲 |
| M8 | Heatmap chart + SSE hook + Dashboard | M5, M7 | 🔲 |
| M9 | Docker + NGINX integration | M1–M8 | 🔲 |

---

## 📦 Module 1 — Project Scaffold + Axios Client

### What to build
- Vite project inside `project/frontend/`
- Install: `react-router-dom`, `axios`, `hls.js`, `recharts`, `@testing-library/react`, `vitest`, `jsdom`
- `src/api/client.js` — Axios instance with `withCredentials: true`, base URL from env, response interceptor that unwraps `SuccessResponse.data`, error interceptor that throws on `ErrorResponse`

### API Contract
```js
// Every backend response follows this envelope:
// Success:  { success: true,  data: T,   message: "..." }
// Error:    { success: false, error: "...", message: "..." }
// Paged:    { success: true,  data: [...], total, page, per_page }

// client.js interceptor should:
// - On success: return response.data.data  (unwrap envelope)
// - On error: throw new Error(response.data.message || "Request failed")
```

### Test Cases — `tests/api/client.test.js`

| # | Test | Expected |
|---|------|----------|
| T1.1 | Axios instance has `withCredentials: true` | Pass |
| T1.2 | Axios instance `baseURL` reads from `VITE_API_BASE_URL` env | Pass |
| T1.3 | Response interceptor unwraps `.data.data` from success envelope | Returns inner data |
| T1.4 | Error interceptor throws `Error` with `message` from error envelope | Error thrown |
| T1.5 | Network error (no response) throws generic error | Error thrown |

---

## 🔐 Module 2 — Auth Context + Login / Register Pages

### What to build
- `src/context/AuthContext.jsx` — React context providing `{ user, loading, login, logout, register }`
- On mount: calls `GET /users/me` to rehydrate session (handles 401 gracefully → user = null)
- `login(email, password)` → calls `POST /auth/login` → sets user state
- `logout()` → calls `POST /auth/logout` → clears user state
- `LoginPage.jsx` — email/password form, redirects to `/` on success
- `RegisterPage.jsx` — name/email/password form, auto-login on success

### API Calls
| Function | Method | Endpoint | Payload |
|----------|--------|----------|---------|
| `getMe` | GET | `/users/me` | — |
| `login` | POST | `/auth/login` | `{ email, password }` |
| `logout` | POST | `/auth/logout` | — |
| `register` | POST | `/auth/register` | `{ name, email, password }` |

### Test Cases — `tests/context/AuthContext.test.jsx`

| # | Test | Expected |
|---|------|----------|
| T2.1 | On mount: calls `GET /users/me`, sets user when 200 | `user` is populated |
| T2.2 | On mount: `GET /users/me` returns 401 → user stays null, no error thrown | `user = null` |
| T2.3 | `login()` calls POST `/auth/login`, sets user on success | `user` state updated |
| T2.4 | `login()` with wrong credentials throws error with message | Error thrown |
| T2.5 | `logout()` calls POST `/auth/logout`, clears user state | `user = null` |
| T2.6 | `register()` calls POST `/auth/register`, then auto-calls login | `user` is set |
| T2.7 | `loading` is `true` during initial session check, `false` after | Loading state correct |

### Test Cases — `tests/components/LoginPage.test.jsx` (via pages)

| # | Test | Expected |
|---|------|----------|
| T2.8 | Login form renders email + password fields + submit button | Fields present |
| T2.9 | Submitting valid credentials calls `login()` and navigates to `/` | Redirect happens |
| T2.10 | Server error shows error message below form | Error message visible |
| T2.11 | Register form renders name + email + password + confirm password | Fields present |
| T2.12 | Password mismatch shows inline validation error | Validation error shown |

---

## 🛡️ Module 3 — ProtectedRoute + Navbar + Routing Shell

### What to build
- `src/App.jsx` — all routes defined with React Router v6 `<Routes>`
- `ProtectedRoute.jsx` — if `user === null && !loading`, redirect to `/login`
- `Navbar.jsx` — shows brand logo, nav links, user name + logout button if logged in, else Login/Register links

### Route Map
| Path | Page | Protected |
|------|------|-----------|
| `/` | `HomePage` | ✅ |
| `/browse` | `BrowsePage` | ✅ |
| `/login` | `LoginPage` | ❌ |
| `/register` | `RegisterPage` | ❌ |
| `/upload` | `UploadPage` | ✅ |
| `/videos/:id` | `PlayerPage` | ✅ |
| `/dashboard` | `DashboardPage` | ✅ |

### Test Cases — `tests/components/ProtectedRoute.test.jsx`

| # | Test | Expected |
|---|------|----------|
| T3.1 | Unauthenticated user visiting `/` redirects to `/login` | Navigate called |
| T3.2 | Authenticated user visiting `/` renders children | Children rendered |
| T3.3 | While `loading = true`, shows spinner (not redirect) | Spinner visible |
| T3.4 | Navbar shows Login + Register links when user is null | Links present |
| T3.5 | Navbar shows username + Logout button when user is set | User name visible |
| T3.6 | Clicking Logout button calls `logout()` | logout() called |

---

## 🎬 Module 4 — Video List Pages (Home + Browse)

### What to build
- `VideoCard.jsx` — thumbnail image, title, creator name, duration badge
- `VideoGrid.jsx` — responsive grid of `VideoCard`s with loading skeleton
- `HomePage.jsx` — two sections: Trending (from `/trending`) + Recommendations (from `/recommendations/:userId`) 
- `BrowsePage.jsx` — paginated list from `GET /videos`, with title search filter

### API Calls
| Function | Method | Endpoint |
|----------|--------|----------|
| `getTrending` | GET | `/trending` |
| `getRecommendations(userId)` | GET | `/recommendations/:userId` |
| `listVideos(page, search)` | GET | `/videos?page=N&search=X` |

### Test Cases — `tests/components/VideoCard.test.jsx`

| # | Test | Expected |
|---|------|----------|
| T4.1 | Renders thumbnail, title, creator, duration | All fields shown |
| T4.2 | Missing thumbnail shows placeholder image | Placeholder rendered |
| T4.3 | Clicking card navigates to `/videos/:id` | Navigate called |
| T4.4 | `HomePage` fetches trending list on mount | API called once |
| T4.5 | `HomePage` renders VideoGrid with trending cards | Cards rendered |
| T4.6 | `HomePage` shows "No recommendations" if list is empty | Empty state shown |
| T4.7 | `BrowsePage` renders paginated video list | Cards rendered |
| T4.8 | `BrowsePage` search input filters videos via API call | API called with search param |
| T4.9 | `BrowsePage` next/prev pagination calls API with page param | API called with page |

---

## 📺 Module 5 — HLS Player + Interaction Tracker

### What to build
- `HlsPlayer.jsx` — wraps a `<video>` element, initialises `hls.js` with the manifest URL, fires interaction events
- `useInteractionTracker.js` — buffers `{ type, videoId, timestamp, videoTs }` events, flushes batch every 3 seconds via `POST /events/interaction`

### Interaction Event Types
| Event | Trigger |
|-------|---------|
| `PLAY` | video `play` event |
| `PAUSE` | video `pause` event |
| `SEEK` | video `seeked` event (videoTs = target time) |
| `REWIND` | `seeked` where new time < previous time |

### API Call
```js
// POST /events/interaction
{
  video_id: "uuid",
  event_type: "PLAY" | "PAUSE" | "SEEK" | "REWIND",
  video_timestamp: 42.5,   // seconds into video
  session_id: "uuid"       // from cookie / localStorage
}
```

### Test Cases — `tests/components/HlsPlayer.test.jsx`

| # | Test | Expected |
|---|------|----------|
| T5.1 | Renders `<video>` element | Video element present |
| T5.2 | Calls `Hls.isSupported()` to decide init path | Correct branch taken |
| T5.3 | If HLS not supported, falls back to native `<video src>` | src attribute set |
| T5.4 | On unmount, calls `hls.destroy()` | Destroy called |

### Test Cases — `tests/hooks/useInteractionTracker.test.js`

| # | Test | Expected |
|---|------|----------|
| T5.5 | Events accumulate in buffer within 3s window | Buffer grows |
| T5.6 | After 3s, buffer is flushed via `POST /events/interaction` | API called |
| T5.7 | Buffer clears after flush | Buffer empty |
| T5.8 | SEEK backward is classified as `REWIND` | event_type = REWIND |
| T5.9 | SEEK forward is classified as `SEEK` | event_type = SEEK |
| T5.10 | On unmount, pending buffer is flushed immediately | API called on cleanup |

---

## 📤 Module 6 — Upload Page + Status Polling

### What to build
- `UploadPage.jsx` — file input (video files only), title + description fields, submit → `POST /videos/upload`, then redirects to player page after status = `ready`
- `useVideoStatus.js` — polls `GET /videos/:id/status` every 3s, stops when status is `ready` or `failed`
- `UploadProgressBar.jsx` — shows current status label (`uploading → processing → ready`)

### Video Status Lifecycle
```
uploading → processing → ready | failed
```

### API Calls
| Function | Method | Endpoint |
|----------|--------|----------|
| `uploadVideo(formData)` | POST | `/videos/upload` (multipart) |
| `getVideoStatus(id)` | GET | `/videos/:id/status` |

### Test Cases — `tests/hooks/useVideoStatus.test.js`

| # | Test | Expected |
|---|------|----------|
| T6.1 | Polls `GET /videos/:id/status` every 3s | API called multiple times |
| T6.2 | Stops polling when status = `ready` | No more API calls |
| T6.3 | Stops polling when status = `failed` | No more API calls |
| T6.4 | Returns current status and error state | Values correct |
| T6.5 | `UploadPage` disables submit button while uploading | Button disabled |
| T6.6 | `UploadPage` shows error if non-video file selected | Validation error |
| T6.7 | After status = `ready`, redirects to `/videos/:id` | Navigate called |
| T6.8 | After status = `failed`, shows failure message with retry option | Error UI shown |

---

## 🤖 Module 7 — Summary Panel

### What to build
- `SummaryPanel.jsx` — fetches `GET /summary/:videoId`, renders:
  - AI-generated summary text
  - Full transcript (collapsible)
  - Key moments list (timestamp + label, clicking seeks player to that time)

### API Call
```js
// GET /summary/:videoId
// Response: { summary, transcript, key_moments: [{ timestamp, label }] }
```

### Test Cases — `tests/components/SummaryPanel.test.jsx`

| # | Test | Expected |
|---|------|----------|
| T7.1 | Fetches `GET /summary/:videoId` on mount | API called |
| T7.2 | Renders summary text when data loads | Summary visible |
| T7.3 | Shows skeleton loader while fetching | Skeleton visible |
| T7.4 | Shows "Summary not available" when 404 | Empty state shown |
| T7.5 | Key moments list renders timestamp + label for each item | Items visible |
| T7.6 | Clicking a key moment calls `onSeek(timestamp)` prop | onSeek called with time |
| T7.7 | Transcript section is collapsible (toggle open/close) | Toggle works |

---

## 🔥 Module 8 — Heatmap Chart + SSE Hook + Dashboard

### What to build
- `useHeatmapSSE.js` — connects to `/heatmap/:videoId/stream` via `EventSource`, updates heatmap data in real-time, reconnects on error
- `HeatmapChart.jsx` — `recharts` `BarChart` where each bar = one 5s segment, colour-coded by intensity (cold=blue, hot=red), clicking a bar seeks video
- `DashboardPage.jsx` — creator-only view (403 redirect for non-creators), shows video list + live heatmap for selected video

### API Calls
| Function | Method | Endpoint |
|----------|--------|----------|
| `getHeatmap(videoId)` | GET | `/heatmap/:videoId` |
| `getLiveHeatmap(videoId)` | GET | `/heatmap/:videoId/live` |
| `getHighlights(videoId)` | GET | `/heatmap/:videoId/highlights` |
| SSE stream | EventSource | `/heatmap/:videoId/stream` |

### Test Cases — `tests/hooks/useHeatmapSSE.test.js`

| # | Test | Expected |
|---|------|----------|
| T8.1 | Opens `EventSource` connection on mount | EventSource created |
| T8.2 | Updates `heatmapData` when SSE message arrives | State updated |
| T8.3 | Closes `EventSource` on unmount | close() called |
| T8.4 | Reconnects after connection error | EventSource re-created |

### Test Cases — `tests/components/HeatmapChart.test.jsx`

| # | Test | Expected |
|---|------|----------|
| T8.5 | Renders a bar for each heatmap segment | Bar count matches |
| T8.6 | High-score segments render with red fill | Red color applied |
| T8.7 | Low-score segments render with blue fill | Blue color applied |
| T8.8 | Clicking a bar calls `onSeek(segmentTime)` prop | onSeek called |
| T8.9 | `DashboardPage` redirects non-creator users to `/` | Navigate called |
| T8.10 | `DashboardPage` shows video list for creator | Videos rendered |
| T8.11 | `DashboardPage` shows live heatmap for selected video | Chart rendered |
| T8.12 | Highlights section lists top 5 segments with timestamps | 5 items shown |

---

## 🐳 Module 9 — Docker + NGINX Integration

### What to build
- `frontend/Dockerfile` — multi-stage: `node:20-alpine` build stage → `nginx:alpine` serve stage
- Update `docker-compose.yml` to add `frontend` service (port 3000 internally, exposed via NGINX)
- Update `nginx/nginx.conf` to add:
  - `location /` → proxy to frontend:3000 (catch-all for React Router)
  - `/api/*` is **not** needed — frontend calls backend routes directly via NGINX (`/auth`, `/videos`, etc.)

### Dockerfile structure
```dockerfile
# Stage 1 — build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build         # outputs to /app/dist

# Stage 2 — serve
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### NGINX frontend config (`frontend/nginx.frontend.conf`)
```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;
  location / {
    try_files $uri $uri/ /index.html;   # React Router fallback
  }
}
```

### Test Cases (Integration / Smoke)

| # | Test | Expected |
|---|------|----------|
| T9.1 | `docker compose up frontend` builds without error | Exit 0 |
| T9.2 | `GET http://localhost` returns React app HTML | 200 + HTML |
| T9.3 | `GET http://localhost/login` returns React app (SPA routing) | 200 + HTML |
| T9.4 | `GET http://localhost/auth/login` proxies to user-service | 422 (no body) |
| T9.5 | Frontend container references correct `VITE_API_BASE_URL` | Env var set |

---

## 🌐 API Reference (Frontend → Backend)

All calls go through **NGINX on port 80**. No direct service ports needed from the browser.

| Module | Method | Path | Auth Required |
|--------|--------|------|---------------|
| Auth | POST | `/auth/register` | ❌ |
| Auth | POST | `/auth/login` | ❌ |
| Auth | POST | `/auth/logout` | ✅ |
| Auth | GET | `/users/me` | ✅ |
| Videos | POST | `/videos/upload` | ✅ |
| Videos | GET | `/videos` | ✅ |
| Videos | GET | `/videos/:id` | ✅ |
| Videos | GET | `/videos/:id/status` | ✅ |
| Streaming | GET | `/stream/:id/index.m3u8` | ✅ |
| Summary | GET | `/summary/:id` | ✅ |
| Trending | GET | `/trending` | ✅ |
| Trending | GET | `/recommendations/:userId` | ✅ |
| Events | POST | `/events/interaction` | ✅ |
| Heatmap | GET | `/heatmap/:id` | ✅ |
| Heatmap | GET | `/heatmap/:id/live` | ✅ |
| Heatmap | GET | `/heatmap/:id/highlights` | ✅ |
| Heatmap | SSE | `/heatmap/:id/stream` | ✅ |

---

## 🧪 Testing Strategy

```
Unit tests    → Vitest + @testing-library/react (mocked axios, mocked EventSource)
Integration   → docker compose smoke tests (curl assertions)
```

**Mock conventions:**
- `vi.mock('../api/client.js')` to mock all API modules
- `vi.useFakeTimers()` for polling/batching hooks
- `global.EventSource = vi.fn(...)` for SSE tests
- `window.Hls = vi.fn(...)` for hls.js tests

**Run tests:**
```bash
cd frontend
npm run test          # Vitest watch mode
npm run test:run      # CI single run
npm run test:coverage # Coverage report
```

---

## ⚙️ Environment Variables

```env
# frontend/.env.example
VITE_API_BASE_URL=http://localhost        # NGINX gateway URL
VITE_SESSION_STORAGE_KEY=session_id      # key for localStorage session tracking
```

---

## ✅ Definition of Done (per module)

A module is **done** when:
1. All components/hooks are implemented
2. All test cases listed above pass (`npm run test:run`)
3. The feature works end-to-end against the running backend (`docker compose up`)
4. No console errors in the browser

---

## 🚀 Quick Start (once built)

```bash
cd project

# Development (with hot reload)
cd frontend && npm run dev
# App runs on http://localhost:5173, calls backend on http://localhost

# Production (Docker)
./start.sh          # starts everything including frontend
# App served on http://localhost
```
