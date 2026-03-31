# Phase 9 — Frontend (React.js)

## Goal
A React.js single-page application that provides the complete user interface: auth, video browsing, video playback with HLS, video upload, and a creator dashboard with the live heatmap visualization.

---

## Service Details

| Property | Value |
|---|---|
| Service name | `frontend` |
| Port | `3000` |
| Framework | React 18 + Vite |
| Video player | `hls.js` |
| Charts | `recharts` |
| HTTP client | `axios` |
| Routing | `react-router-dom` v6 |

---

## Folder Structure

```
frontend/
├── Dockerfile
├── vite.config.js
├── package.json
├── index.html
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── api/
    │   ├── auth.js          ← register, login, logout, me
    │   ├── videos.js        ← upload, fetch, list, status poll
    │   ├── streaming.js     ← HLS manifest URL builder
    │   ├── summary.js       ← fetch summary + key moments
    │   ├── trending.js      ← fetch trending list
    │   ├── heatmap.js       ← fetch heatmap, SSE connection
    │   └── events.js        ← fire interaction events (batched)
    ├── components/
    │   ├── Navbar.jsx
    │   ├── VideoCard.jsx
    │   ├── HeatmapChart.jsx     ← recharts bar chart overlay
    │   └── KeyMomentsPanel.jsx
    └── pages/
        ├── Login.jsx
        ├── Register.jsx
        ├── Home.jsx             ← trending grid
        ├── VideoPlayer.jsx      ← HLS player + summary + interactions
        ├── Upload.jsx           ← upload form + status polling
        ├── Dashboard.jsx        ← creator dashboard + heatmap
        └── Browse.jsx           ← search + filter
```

---

## Pages

### 1. Login & Register
- Forms with validation
- On success: cookie set by backend, redirect to Home
- No JWT in localStorage — session cookie is HTTP-only
- **All axios calls must use `withCredentials: true`** so the browser sends the HttpOnly session cookie on cross-origin requests (see API client setup below)

### 2. Home (Trending)
```
┌──────────────────────────────────────────────────────────┐
│  🎬 VideoStream                          [Login] [Upload] │
├──────────────────────────────────────────────────────────┤
│  🔥 Trending Now                                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐            │
│  │ thumb  │ │ thumb  │ │ thumb  │ │ thumb  │            │
│  │ Title  │ │ Title  │ │ Title  │ │ Title  │            │
│  │ ★ 4821 │ │ ★ 3102 │ │ ★ 1890 │ │ ★  945 │            │
│  └────────┘ └────────┘ └────────┘ └────────┘            │
└──────────────────────────────────────────────────────────┘
```
- Fetches from `GET /trending`
- Each card links to `/video/:id`

### 3. Video Player Page
```
┌──────────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────────┐  │
│  │                                                    │  │
│  │              HLS VIDEO PLAYER (hls.js)             │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│  ▶ 0:00 ─────────────────────────── 9:02               │
│                                                          │
│  📝 AI Summary                                           │
│  "This video explains recursive descent parsers..."      │
│                                                          │
│  🕐 Key Moments                                          │
│  [2:22 - Introduction]  [4:40 - Live Demo]              │
└──────────────────────────────────────────────────────────┘
```

**Interaction Event Firing:**
```javascript
// api/events.js — batch and send every 3 seconds
const eventBuffer = [];

export function trackEvent(videoId, eventType, videoTs, seekFrom = null) {
  eventBuffer.push({ videoId, eventType, videoTs, seekFrom,
                     clientTime: Math.floor(Date.now() / 1000) });
}

setInterval(async () => {
  if (eventBuffer.length === 0) return;
  const batch = eventBuffer.splice(0, eventBuffer.length);
  for (const event of batch) {
    await axios.post("/events/interaction", event)
      .catch(() => eventBuffer.push(event));  // retry on failure
  }
}, 3000);
```

**hls.js Events to Track:**

| hls.js Event | Fires When | Our eventType |
|---|---|---|
| `hls.on(Hls.Events.LEVEL_SWITCHED)` | Quality change | — (internal) |
| Player `pause` event | User hits pause | `PAUSE` |
| Player `play` event | User hits play | `PLAY` — also inserts into watch_history via `POST /events/interaction` |
| Player `seeking` event | User seeks | `SEEK` |
| Custom: seeking backwards > 5s | User rewinds | `REWIND` |
| `hls.on(Hls.Events.BUFFER_STALLED)` | Buffering | `BUFFER` |

### 4. Upload Page
```
┌──────────────────────────────────────────────┐
│  Upload Video                                │
│                                              │
│  Title: [_________________________]          │
│  Description: [___________________]          │
│  File: [  Choose File  ] video.mp4           │
│                                              │
│  [ Upload ]                                  │
│                                              │
│  ⏳ Status: processing... (polling)          │
│  ✅ Status: ready! View →                    │
└──────────────────────────────────────────────┘
```
- Status polling via `GET /videos/:id/status` every 3s
- Stops polling when status = `ready` or `failed`

### 5. Creator Dashboard

```
┌──────────────────────────────────────────────────────────┐
│  📊 Dashboard — "How I Built a Compiler" (42min)         │
│                                                          │
│  Views: 128,493  |  Avg Watch: 28min  |  Rewatch: 23%   │
│                                                          │
│  🔥 ENGAGEMENT HEATMAP (live)                            │
│  0:00                          42:00                     │
│  [░░░▒▒▓▓███████▓▓▒▒░░░▒▒▓▓████████░░░░░░▒▒▒▒░░]       │
│                                                          │
│  ⭐ Top Rewatched Moments                                │
│  1. 2:20–2:25  "Recursive descent demo"  — 312 rewinds  │
│  2. 8:40–8:45  "Memory layout explained" — 198 rewinds  │
│                                                          │
│  💡 Tip: Segment at 2:20 has 67% rewatch rate.          │
│     Consider making this a standalone short!             │
└──────────────────────────────────────────────────────────┘
```

**HeatmapChart Component (recharts):**
```jsx
// components/HeatmapChart.jsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from "recharts";

export default function HeatmapChart({ segments }) {
  const getColor = (count) => {
    if (count > 200) return "#ef4444";   // red — very hot
    if (count > 100) return "#f97316";   // orange — hot
    if (count > 50)  return "#eab308";   // yellow — warm
    return "#22c55e";                    // green — cool
  };

  return (
    <BarChart width={900} height={120} data={segments}>
      <XAxis dataKey="label" hide />
      <YAxis hide />
      <Tooltip formatter={(v) => [`${v} interactions`]} />
      <Bar dataKey="totalInteractions">
        {segments.map((seg, i) => (
          <Cell key={i} fill={getColor(seg.totalInteractions)} />
        ))}
      </Bar>
    </BarChart>
  );
}
```

**Live SSE Connection for Dashboard:**
```javascript
// api/heatmap.js
export function connectHeatmapStream(videoId, onUpdate) {
  const es = new EventSource(`/heatmap/${videoId}/stream`);
  es.onmessage = (e) => {
    const update = JSON.parse(e.data);
    onUpdate(update);   // update React state → re-render chart
  };
  return () => es.close();  // cleanup function
}
```

### 6. Browse / Search
- `GET /videos?title=<query>` (server-side search)
- Filter by: All / Trending / New
- Infinite scroll or pagination

---

## Dockerfile

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx-frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
```

---

## package.json (key deps)

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

---

## API Client Setup

All HTTP calls go through a single axios instance that handles the `SuccessResponse` envelope and global auth redirects.

```js
// api/client.js
import axios from "axios";

const client = axios.create({ baseURL: "/", withCredentials: true });

client.interceptors.response.use(
  res => res.data.data ?? res.data,
  err => {
    const errorCode = err.response?.data?.error;
    if (errorCode === "UNAUTHORIZED") window.location.href = "/login";
    return Promise.reject(err.response?.data ?? err);
  }
);

export default client;
```

Every `api/*.js` module imports `client` instead of `axios` directly.

---

## Error Handling per Page

| Page | API call | Error code | UI behaviour |
|---|---|---|---|
| Video Player | `GET /summary/:videoId` | `SUMMARY_NOT_FOUND` (404) | Show "Summary not yet available" |
| Upload | `POST /videos/upload` | `VALIDATION_ERROR` (422) | Show per-field errors from `detail` array |
| Dashboard | `GET /heatmap/:videoId` | `FORBIDDEN` (403) | Show "You can only view heatmaps for your own videos" |
