# 📁 Task Files Index

> One task file per phase. Each file breaks the phase into atomic, verifiable tasks.
> **Convention:** Nothing is marked done without a passing test.

## Phase Files

| Phase | File | Focus | Tasks |
|---|---|---|---|
| 1 | [phase-1.md](./phase-1.md) | Infrastructure & Skeleton | 12 |
| 2 | [phase-2.md](./phase-2.md) | User Service | 21 |
| 3 | [phase-3.md](./phase-3.md) | Video Service | 18 |
| 4 | [phase-4.md](./phase-4.md) | Processing Pipeline (encoding + thumbnail workers) | 22 |
| 5 | [phase-5.md](./phase-5.md) | Streaming Service (HLS) | 13 |
| 6 | [phase-6.md](./phase-6.md) | AI Summarization (Whisper + BART) | 20 |
| 7 | [phase-7.md](./phase-7.md) | Trending & Recommendations | 20 |
| 8 | [phase-8.md](./phase-8.md) | Heatmap Engine (event-ingestion + aggregator + API) | 39 |
| 9 | [phase-9.md](./phase-9.md) | Frontend (React + Vite) | 22 |
| 10 | [phase-10.md](./phase-10.md) | Integration & Final Documentation | 17 |

**Total tasks across all phases: ~204**

---

## How to Use These Files

1. **Start a session** — read `docs/COPILOT.md` for the session protocol
2. **Pick a phase** — open the corresponding file here
3. **Work through tasks top-to-bottom** — each task has exact commands and acceptance criteria
4. **Test before marking done** — run the `Test / Verify` block at the end of each task
5. **Ask what to do next** after completing a phase

## Task Status Legend

| Symbol | Meaning |
|---|---|
| ⬜ | Pending — not yet started |
| 🔄 | In progress — currently being worked on |
| ✅ | Done — tested and verified |
| ❌ | Blocked — cannot proceed (reason documented in task) |

---

## Reference Docs

These provide the underlying design behind each task file:

| Doc | What it covers |
|---|---|
| [`docs/HLD.md`](../HLD.md) | Full system architecture diagram |
| [`docs/database-design.md`](../database-design.md) | Schema for PostgreSQL, Redis, MongoDB |
| [`docs/lld.md`](../lld.md) | Per-service low-level design |
| [`docs/unique-feature.md`](../unique-feature.md) | Heatmap Engine deep-dive |
| [`docs/phases/shared-patterns.md`](../phases/shared-patterns.md) | Code conventions all services follow |
| [`docs/phases/phase-10-integration.md`](../phases/phase-10-integration.md) | Full docker-compose.yml + E2E curl script |
