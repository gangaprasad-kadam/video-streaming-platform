# 📋 Phase 9 — Frontend (React + Vite) Task File

> **Goal:** React 18 + Vite SPA providing: auth (login/register), video browsing,
> HLS video player with interaction tracking, upload with status polling,
> AI summary display, and creator dashboard with live heatmap visualization.

**Reference doc:** [`docs/phases/phase-9-frontend.md`](../phases/phase-9-frontend.md)
**Depends on:** All previous phases ✅ (all backend APIs must be running)
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

| # | Task | Status |
|---|---|---|
| 1 | Bootstrap Vite + React project | ⬜ |
| 2 | Write `Dockerfile` (multi-stage build + nginx) | ⬜ |
| 3 | Write `vite.config.js` (proxy to backend) | ⬜ |
| 4 | Write `src/api/client.js` (axios instance + interceptors) | ⬜ |
| 5 | Write `src/api/auth.js` | ⬜ |
| 6 | Write `src/api/videos.js` | ⬜ |
| 7 | Write `src/api/events.js` (batched interaction tracker) | ⬜ |
| 8 | Write `src/api/heatmap.js` (REST + SSE) | ⬜ |
| 9 | Write `src/api/trending.js` + `src/api/summary.js` | ⬜ |
| 10 | Write `src/App.jsx` + routes | ⬜ |
| 11 | Write `src/components/Navbar.jsx` | ⬜ |
| 12 | Write `src/components/VideoCard.jsx` | ⬜ |
| 13 | Write `src/components/HeatmapChart.jsx` | ⬜ |
| 14 | Write `src/components/KeyMomentsPanel.jsx` | ⬜ |
| 15 | Write `src/pages/Login.jsx` + `Register.jsx` | ⬜ |
| 16 | Write `src/pages/Home.jsx` (trending grid) | ⬜ |
| 17 | Write `src/pages/VideoPlayer.jsx` (HLS + events) | ⬜ |
| 18 | Write `src/pages/Upload.jsx` (upload + status polling) | ⬜ |
| 19 | Write `src/pages/Dashboard.jsx` (heatmap + highlights) | ⬜ |
| 20 | Write `src/pages/Browse.jsx` (search + filter) | ⬜ |
| 21 | Add `frontend` to `docker-compose.yml` | ⬜ |
| 22 | Manual smoke test — all pages navigable | ⬜ |

---

## Task Details

---

### ✅ Task 1 — Bootstrap Vite + React Project

**What:** Initialize the React project inside the `frontend/` directory.

```bash
cd frontend
npm create vite@latest . -- --template react
npm install
npm install react-router-dom axios hls.js recharts
```

**Verify `package.json` has these deps:**
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "axios": "^1.6.7",
    "hls.js": "^1.5.7",
    "recharts": "^2.12.2"
  },
  "devDependencies": {
    "vite": "^5.1.4",
    "@vitejs/plugin-react": "^4.2.1"
  }
}
```

**Test / Verify:**
```bash
cd frontend
npm run dev &
sleep 5
curl -f http://localhost:5173
# Should return HTML (Vite dev server)
kill %1
```

**Acceptance criteria:**
- [ ] `package.json` has all 6 dependencies
- [ ] `npm run dev` starts without errors
- [ ] `npm run build` exits 0 (production build works)

---

### ✅ Task 2 — Write `Dockerfile`

**File:** `frontend/Dockerfile`

**Multi-stage build:**
```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx-frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
```

**`frontend/nginx-frontend.conf`:**
```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;
    index index.html;

    # SPA — all unknown paths → index.html (react-router handles routing)
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**Test / Verify:**
```bash
docker build -t frontend-test frontend/
docker run -d -p 3000:3000 --name fe-test frontend-test
sleep 3
curl -f http://localhost:3000
docker stop fe-test && docker rm fe-test
```

**Acceptance criteria:**
- [ ] Docker build exits 0
- [ ] Container serves HTML on port 3000
- [ ] Unknown routes (`/video/abc`) return `index.html` (SPA routing)

---

### ✅ Task 3 — Write `vite.config.js`

**File:** `frontend/vite.config.js`

**What:** Proxy all API calls from dev server to backend (avoids CORS in development).

```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth":    { target: "http://localhost:8001", changeOrigin: true },
      "/users":   { target: "http://localhost:8001", changeOrigin: true },
      "/videos":  { target: "http://localhost:8002", changeOrigin: true },
      "/stream":  { target: "http://localhost:8003", changeOrigin: true },
      "/summary": { target: "http://localhost:8004", changeOrigin: true },
      "/trending":{ target: "http://localhost:8005", changeOrigin: true },
      "/recommendations": { target: "http://localhost:8005", changeOrigin: true },
      "/events":  { target: "http://localhost:8006", changeOrigin: true },
      "/heatmap": { target: "http://localhost:8007", changeOrigin: true },
    }
  }
});
```

**Test / Verify:**
```bash
cd frontend
node -e "
const cfg = require('./vite.config.js');
const proxy = cfg.default.server?.proxy ?? cfg.server?.proxy;
console.log(JSON.stringify(Object.keys(proxy)));
"
# Should print all 9 proxy routes
```

**Acceptance criteria:**
- [ ] All 9 routes proxied
- [ ] Development proxy works (`npm run dev` + `curl localhost:5173/auth/...`)

---

### ✅ Task 4 — Write `src/api/client.js`

**File:** `frontend/src/api/client.js`

**What:** Shared axios instance. Handles `SuccessResponse` envelope unwrapping + global 401 redirect.

```javascript
import axios from "axios";

const client = axios.create({
  baseURL: "/",
  withCredentials: true,  // send HttpOnly session cookie on every request
});

// Unwrap SuccessResponse envelope: { data: {...}, message: "success" } → {...}
client.interceptors.response.use(
  (res) => res.data?.data ?? res.data,
  (err) => {
    const errorCode = err.response?.data?.error;
    if (errorCode === "UNAUTHORIZED") {
      window.location.href = "/login";
    }
    return Promise.reject(err.response?.data ?? err);
  }
);

export default client;
```

**Key rules:**
- `withCredentials: true` on every request (session cookie is HttpOnly)
- Unwrap `data.data` from `SuccessResponse` envelope
- 401 → redirect to `/login`

**Test / Verify:**
```bash
cd frontend
node -e "
// Quick check: client exports axios instance
const {default: client} = require('./src/api/client.js');
console.log(typeof client.get === 'function' ? 'Client OK' : 'FAIL');
" 2>/dev/null || echo "Cannot run ESM in node directly — verified by build"
npm run build 2>&1 | grep -E "error|Error" || echo "Build OK — no errors"
```

**Acceptance criteria:**
- [ ] `withCredentials: true` set
- [ ] Response interceptor unwraps `data.data`
- [ ] 401 redirects to `/login`
- [ ] `npm run build` exits 0

---

### ✅ Task 5 — Write `src/api/auth.js`

**File:** `frontend/src/api/auth.js`

```javascript
import client from "./client";

export const register = (data) => client.post("/auth/register", data);
export const login    = (data) => client.post("/auth/login", data);
export const logout   = ()     => client.post("/auth/logout");
export const getMe    = ()     => client.get("/users/me");
```

**Test / Verify:**
```bash
cd frontend && npm run build 2>&1 | grep -c "error" || echo "0 errors in build"
```

**Acceptance criteria:**
- [ ] All 4 functions exported
- [ ] `login` does NOT store anything in localStorage (backend sets HttpOnly cookie)
- [ ] `npm run build` exits 0

---

### ✅ Task 6 — Write `src/api/videos.js`

**File:** `frontend/src/api/videos.js`

```javascript
import client from "./client";

export const uploadVideo = (formData) =>
  client.post("/videos/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });

export const getVideo       = (id)              => client.get(`/videos/${id}`);
export const getVideoStatus = (id)              => client.get(`/videos/${id}/status`);
export const listVideos     = (params)          => client.get("/videos", { params });
export const patchVideo     = (id, data)        => client.patch(`/videos/${id}`, data);
```

**Acceptance criteria:**
- [ ] `uploadVideo` sets `multipart/form-data` header
- [ ] All 5 functions exported
- [ ] `npm run build` exits 0

---

### ✅ Task 7 — Write `src/api/events.js`

**File:** `frontend/src/api/events.js`

**What:** Buffers interaction events and sends them every 3 seconds.

```javascript
import client from "./client";

const eventBuffer = [];

export function trackEvent(videoId, eventType, videoTs, seekFrom = null) {
  eventBuffer.push({
    videoId,
    eventType,
    videoTs,
    seekFrom,
    clientTime: Math.floor(Date.now() / 1000),
  });
}

// Flush buffer every 3 seconds
setInterval(async () => {
  if (eventBuffer.length === 0) return;
  const batch = eventBuffer.splice(0, eventBuffer.length);
  for (const event of batch) {
    try {
      await client.post("/events/interaction", event);
    } catch {
      eventBuffer.push(event);  // retry failed events
    }
  }
}, 3000);
```

**hls.js event mapping (used in VideoPlayer.jsx):**

| Player event | Our eventType |
|---|---|
| `play` | `PLAY` |
| `pause` | `PAUSE` |
| `seeking` (backward > 5s) | `REWIND` |
| `seeking` | `SEEK` |
| `Hls.Events.BUFFER_STALLED` | `BUFFER` |

**Acceptance criteria:**
- [ ] `trackEvent` buffers without immediate API call
- [ ] Events flushed every 3 seconds
- [ ] Failed events pushed back to buffer for retry
- [ ] `npm run build` exits 0

---

### ✅ Task 8 — Write `src/api/heatmap.js`

**File:** `frontend/src/api/heatmap.js`

```javascript
import client from "./client";

export const getHeatmap    = (videoId) => client.get(`/heatmap/${videoId}`);
export const getHighlights = (videoId) => client.get(`/heatmap/${videoId}/highlights`);
export const getLiveHeatmap= (videoId) => client.get(`/heatmap/${videoId}/live`);

// SSE connection — returns cleanup function
export function connectHeatmapStream(videoId, onUpdate) {
  const es = new EventSource(`/heatmap/${videoId}/stream`, {
    withCredentials: true
  });
  es.onmessage = (e) => {
    try {
      const update = JSON.parse(e.data);
      onUpdate(update);
    } catch {}
  };
  es.onerror = () => es.close();
  return () => es.close();  // call this in React cleanup (useEffect return)
}
```

**Acceptance criteria:**
- [ ] SSE uses `EventSource` (not axios)
- [ ] `withCredentials: true` on SSE connection
- [ ] `connectHeatmapStream` returns cleanup function for `useEffect`
- [ ] `npm run build` exits 0

---

### ✅ Task 9 — Write `src/api/trending.js` + `src/api/summary.js`

**`trending.js`:**
```javascript
import client from "./client";
export const getTrending       = (limit = 10) => client.get("/trending", { params: { limit } });
export const getRecommendations= ()           => client.get("/recommendations");
```

**`summary.js`:**
```javascript
import client from "./client";
export const getSummary = (videoId) => client.get(`/summary/${videoId}`);
```

**Acceptance criteria:**
- [ ] Both files exist, all 3 functions exported
- [ ] `npm run build` exits 0

---

### ✅ Task 10 — Write `src/App.jsx` + Routes

**File:** `frontend/src/App.jsx`

**Routes:**

| Path | Component | Auth required |
|---|---|---|
| `/` | `Home` | No |
| `/login` | `Login` | No |
| `/register` | `Register` | No |
| `/video/:id` | `VideoPlayer` | No |
| `/upload` | `Upload` | Yes (redirect to `/login`) |
| `/dashboard/:videoId` | `Dashboard` | Yes |
| `/browse` | `Browse` | No |

```jsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Login from "./pages/Login";
// ... etc

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/video/:id" element={<VideoPlayer />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/dashboard/:videoId" element={<Dashboard />} />
        <Route path="/browse" element={<Browse />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**Test / Verify:**
```bash
cd frontend && npm run build 2>&1 | grep -E "^✓|error" | head -5
```

**Acceptance criteria:**
- [ ] All 7 routes defined
- [ ] `Navbar` rendered on every page
- [ ] `npm run build` exits 0

---

### ✅ Task 11 — Write `src/components/Navbar.jsx`

**What:** Top navigation bar. Shows logo, links, and auth state.

**Logged-out state:** Logo · Browse · [Login] · [Register]
**Logged-in state:** Logo · Browse · [Upload] · [Dashboard] · [Logout]

**Auth state:** Fetch `GET /users/me` on mount. If 401 → show logged-out nav.

```jsx
export default function Navbar() {
  const [user, setUser] = useState(null);
  useEffect(() => {
    getMe().then(setUser).catch(() => setUser(null));
  }, []);
  // ... render nav based on user state
}
```

**Acceptance criteria:**
- [ ] Shows correct nav items based on auth state
- [ ] Logout button calls `logout()` + redirects to `/`
- [ ] `npm run build` exits 0

---

### ✅ Task 12 — Write `src/components/VideoCard.jsx`

**What:** Reusable card showing thumbnail, title, and trending score.

**Props:** `{ video: { id, title, thumbnail_path, score, rank } }`

**Layout:**
```
┌─────────────────┐
│   [thumbnail]   │
│  Title text...  │
│  ★ 4,821        │
└─────────────────┘
```

**Thumbnail URL:** `/stream/{videoId}/thumbnail.jpg` (served from nginx → streaming-service)
**Click → navigate** to `/video/{id}`

**Acceptance criteria:**
- [ ] Thumbnail shown (with fallback placeholder if `null`)
- [ ] Click navigates to video player page
- [ ] Score displayed with `★` icon
- [ ] `npm run build` exits 0

---

### ✅ Task 13 — Write `src/components/HeatmapChart.jsx`

**What:** recharts `BarChart` rendered as a color-coded heatmap strip.

**Color coding:**

| Interactions | Color | Meaning |
|---|---|---|
| > 200 | `#ef4444` (red) | Very hot |
| > 100 | `#f97316` (orange) | Hot |
| > 50 | `#eab308` (yellow) | Warm |
| ≤ 50 | `#22c55e` (green) | Cool |

**Props:** `{ segments: [{ segmentId, start, end, totalInteractions }] }`

```jsx
import { BarChart, Bar, XAxis, Tooltip, Cell } from "recharts";

export default function HeatmapChart({ segments }) {
  const getColor = (count) => {
    if (count > 200) return "#ef4444";
    if (count > 100) return "#f97316";
    if (count > 50)  return "#eab308";
    return "#22c55e";
  };

  return (
    <BarChart width={900} height={120} data={segments}>
      <XAxis dataKey="start" tickFormatter={(v) => `${Math.floor(v/60)}:${String(v%60).padStart(2,'0')}`} />
      <Tooltip formatter={(v) => [`${v} interactions`]} />
      <Bar dataKey="totalInteractions">
        {segments.map((seg, i) => <Cell key={i} fill={getColor(seg.totalInteractions)} />)}
      </Bar>
    </BarChart>
  );
}
```

**Acceptance criteria:**
- [ ] Uses `recharts` `BarChart`
- [ ] Color changes based on interaction count
- [ ] Tooltip shows interaction count on hover
- [ ] `npm run build` exits 0

---

### ✅ Task 14 — Write `src/components/KeyMomentsPanel.jsx`

**What:** Displays AI-extracted key moments as clickable timestamps.

**Props:** `{ moments: [{ timestamp, label }], onSeek: (time) => void }`

```jsx
export default function KeyMomentsPanel({ moments, onSeek }) {
  return (
    <div>
      <h3>🕐 Key Moments</h3>
      {moments.map((m, i) => (
        <button key={i} onClick={() => onSeek(m.timestamp)}>
          {formatTime(m.timestamp)} — {m.label}
        </button>
      ))}
    </div>
  );
}
```

**`formatTime(seconds)`:** `"2:22"` format

**Acceptance criteria:**
- [ ] Each moment is a clickable button
- [ ] Clicking calls `onSeek(timestamp)` (VideoPlayer uses this to seek the video)
- [ ] Time formatted as `M:SS`
- [ ] `npm run build` exits 0

---

### ✅ Task 15 — Write `src/pages/Login.jsx` + `Register.jsx`

**Login.jsx:**
- Form: `email`, `password`
- Calls `login(data)` → on success redirect to `/`
- On 401: show "Invalid email or password"

**Register.jsx:**
- Form: `username`, `email`, `password`
- Calls `register(data)` → on success redirect to `/login`
- On 409: show "Email already registered"
- Client-side validation: password min 8 chars

**Test / Verify:**
```bash
cd frontend && npm run build 2>&1 | grep -c "error" || echo "Build OK"
```

**Acceptance criteria:**
- [ ] Form validation (empty fields, short password)
- [ ] API errors shown to user (not just console.error)
- [ ] Successful register → redirect to login
- [ ] Successful login → redirect to home
- [ ] `npm run build` exits 0

---

### ✅ Task 16 — Write `src/pages/Home.jsx`

**What:** Trending video grid. Fetches on mount, renders `VideoCard` components.

```jsx
export default function Home() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTrending(12).then(setVideos).finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading...</p>;
  return (
    <div>
      <h1>🔥 Trending Now</h1>
      <div className="grid">
        {videos.map(v => <VideoCard key={v.video_id} video={v} />)}
      </div>
    </div>
  );
}
```

**Acceptance criteria:**
- [ ] Fetches trending on mount
- [ ] Loading state shown
- [ ] Empty state handled ("No videos yet")
- [ ] Each card links to `/video/{id}`

---

### ✅ Task 17 — Write `src/pages/VideoPlayer.jsx`

**What:** The core playback page. HLS player + AI summary + interaction tracking.

**Steps to implement:**
1. Fetch `GET /videos/:id` for metadata
2. Fetch `GET /summary/:id` for summary + key moments
3. Initialize `hls.js` player pointing to `/stream/:id/index.m3u8`
4. Wire player events to `trackEvent()`
5. Render `KeyMomentsPanel` with `onSeek` that calls `video.currentTime = t`

**HLS player initialization:**
```javascript
useEffect(() => {
  const video = videoRef.current;
  const hls = new Hls();
  hls.loadSource(`/stream/${videoId}/index.m3u8`);
  hls.attachMedia(video);

  // Track events
  video.addEventListener("play",  () => trackEvent(videoId, "PLAY",  video.currentTime));
  video.addEventListener("pause", () => trackEvent(videoId, "PAUSE", video.currentTime));
  video.addEventListener("seeking", () => {
    // Detect REWIND: new position is > 5s behind previous
    const diff = prevTime.current - video.currentTime;
    trackEvent(videoId, diff > 5 ? "REWIND" : "SEEK", video.currentTime);
    prevTime.current = video.currentTime;
  });
  hls.on(Hls.Events.BUFFER_STALLED, () => trackEvent(videoId, "BUFFER", video.currentTime));

  return () => { hls.destroy(); };
}, [videoId]);
```

**Error states:**
- Video status `processing` → show "Video is being processed, please wait..."
- Summary 404 → show "AI summary not yet available"

**Acceptance criteria:**
- [ ] HLS video plays in browser (confirmed manually)
- [ ] `PLAY`, `PAUSE`, `SEEK`, `REWIND`, `BUFFER` events tracked
- [ ] REWIND correctly detected (seeking backward > 5s)
- [ ] Key moments panel visible with clickable timestamps
- [ ] Summary shown (or "not available" message)
- [ ] `npm run build` exits 0

---

### ✅ Task 18 — Write `src/pages/Upload.jsx`

**What:** Upload form + status polling.

```jsx
export default function Upload() {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState(null);
  const [videoId, setVideoId] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title);
    const result = await uploadVideo(formData);
    setVideoId(result.id);
    setStatus("uploading");
    startPolling(result.id);
  };

  const startPolling = (id) => {
    const interval = setInterval(async () => {
      const s = await getVideoStatus(id);
      setStatus(s.status);
      if (s.status === "ready" || s.status === "failed") {
        clearInterval(interval);
      }
    }, 3000);
  };
  // ... render form + status display
}
```

**Status display:**
- `uploading` → "⏳ Uploading..."
- `processing` → "⚙️ Processing... (encoding + thumbnail)"
- `ready` → "✅ Ready! [Watch Video →]"
- `failed` → "❌ Processing failed. Please try again."

**Acceptance criteria:**
- [ ] File input accepts video files only (`accept="video/*"`)
- [ ] Polls every 3 seconds after upload
- [ ] Stops polling when `ready` or `failed`
- [ ] Shows link to player when `ready`
- [ ] 422 validation errors displayed per-field

---

### ✅ Task 19 — Write `src/pages/Dashboard.jsx`

**What:** Creator dashboard with live heatmap + highlights.

**Steps:**
1. Fetch `GET /heatmap/:videoId` → segments data
2. Fetch `GET /heatmap/:videoId/highlights` → top 5 moments
3. Connect SSE with `connectHeatmapStream(videoId, onUpdate)`
4. On SSE update: `setSegments(prev => updateSegment(prev, update))`
5. Render `HeatmapChart` with segments
6. Render highlights list

**SSE live update handler:**
```javascript
const onUpdate = ({ segId, eventType }) => {
  setSegments(prev => prev.map(seg =>
    seg.segmentId === segId
      ? { ...seg, totalInteractions: seg.totalInteractions + 1 }
      : seg
  ));
};

useEffect(() => {
  const cleanup = connectHeatmapStream(videoId, onUpdate);
  return cleanup;  // disconnect SSE on unmount
}, [videoId]);
```

**Error states:**
- 403 → show "You can only view heatmaps for your own videos"
- 401 → redirect to login (handled by client.js interceptor)

**Acceptance criteria:**
- [ ] `HeatmapChart` rendered with segment data
- [ ] SSE connection established on mount, cleaned up on unmount
- [ ] Chart updates live as SSE messages arrive (without page refresh)
- [ ] Top 5 highlights list shown with rank + rewind count
- [ ] 403 error displayed with helpful message

---

### ✅ Task 20 — Write `src/pages/Browse.jsx`

**What:** Video search + filter page with pagination.

**Features:**
- Search box → `GET /videos?title=<query>`
- Filter tabs: All / Trending / New
- Video grid with `VideoCard` components
- Pagination: "Load more" button

```jsx
export default function Browse() {
  const [query, setQuery] = useState("");
  const [videos, setVideos] = useState([]);
  const [page, setPage] = useState(1);

  const search = async () => {
    const result = await listVideos({ title: query, page, limit: 12 });
    setVideos(result.items ?? []);
  };

  useEffect(() => { search(); }, [query, page]);
  // ...
}
```

**Acceptance criteria:**
- [ ] Search triggers API call on input change (debounced 300ms)
- [ ] Pagination loads next page
- [ ] Empty state: "No videos found"

---

### ✅ Task 21 — Add `frontend` to `docker-compose.yml`

```yaml
frontend:
  build: ./frontend
  ports:
    - "3000:3000"
  depends_on:
    - user-service
    - video-service
    - streaming-service
    - summarization-service
    - trending-service
    - event-ingestion
    - heatmap-api
```

**Test / Verify:**
```bash
docker compose config --quiet
docker compose build frontend
docker compose up -d frontend
sleep 5
curl -f http://localhost:3000
curl -f http://localhost:3000/login    # SPA route → should return index.html
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0
- [ ] `GET http://localhost:3000` returns HTML
- [ ] `GET http://localhost:3000/login` returns `index.html` (not 404)

---

### ✅ Task 22 — Manual Smoke Test — All Pages Navigable

**Open browser and verify each page:**

| Page | URL | What to verify |
|---|---|---|
| Home | `http://localhost` | Trending grid renders |
| Register | `http://localhost/register` | Form submits, redirects to login |
| Login | `http://localhost/login` | Form submits, redirects to home |
| Browse | `http://localhost/browse` | Video cards visible |
| Upload | `http://localhost/upload` | Upload form works, status polling works |
| Video Player | `http://localhost/video/{id}` | HLS video plays, summary shown |
| Dashboard | `http://localhost/dashboard/{id}` | Heatmap chart renders |

**Acceptance criteria:**
- [ ] All 7 pages render without JS errors in browser console
- [ ] HLS video plays in Chrome/Firefox
- [ ] Upload → processing → ready flow completes end-to-end
- [ ] Dashboard heatmap updates when you play the video in another tab

---

## Phase Complete Checklist

Before marking Phase 9 as ✅ done in `COPILOT.md`:

- [ ] All 22 tasks above are ✅ done
- [ ] `npm run build` exits 0 with no errors
- [ ] All 7 pages render without JS console errors
- [ ] HLS video plays in browser (confirmed manually)
- [ ] REWIND event correctly detected (seeking backward > 5s)
- [ ] Upload → `ready` flow works end-to-end
- [ ] Dashboard heatmap chart renders and updates live via SSE
- [ ] `docker compose build frontend` exits 0
- [ ] `http://localhost` (via NGINX gateway) serves the frontend
