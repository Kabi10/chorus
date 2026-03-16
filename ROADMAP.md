# Parallel Build Plan — KaiView + Chorus
> Last updated: 2026-03-15

Two open source projects built in parallel. Each phase is designed to be tackled together — one session per phase pair.

---

## Projects

| | KaiView | Chorus |
|---|---|---|
| **Repo** | github.com/Kabi10/kaiview | github.com/Kabi10/chorus |
| **Purpose** | AI-powered developer OS | Multi-AI consultation tool |
| **Stack** | Python, FastAPI, Vanilla JS, SQLite | Python, FastAPI, Playwright, D3.js |
| **Port** | 3737 | 4747 |
| **Status** | v1 live | Scaffolded |

---

## Phase Overview

```
PHASE 1 ──── Foundation          ←── YOU ARE HERE
PHASE 2 ──── Intelligence
PHASE 3 ──── Power Features
PHASE 4 ──── Polish & Launch
```

---

## PHASE 1 — Foundation

### KaiView — Fix the Base

> Goal: Make the existing v1 production-grade before adding features.

- [ ] **SQLite migration** — replace `projects_meta.json` with SQLite via `aiosqlite`
  - Tables: `projects`, `sessions`, `tasks`, `ai_logs`
  - Add `schema_version` field
  - Auto-migrate existing JSON on first run
- [ ] **Resume / Park system**
  - `Resume` button per card → opens VS Code + copies AI context + shows last session note
  - `Park` button → saves current task, next action, note with timestamp
  - Store in `sessions` table
- [ ] **3-Lens home view**
  - `Active Now` — git commits in last 48h or manually flagged
  - `Needs Attention` — stale progress, dirty files, no commits in 7+ days
  - `Neglected` — no commits in 30+ days, not paused/archived
  - Replaces flat alphabetical grid
- [ ] **Staleness score** — computed per project (days since commit, status weight, dirty state)
- [ ] **Background git watcher** — poll every 60s, push updates via WebSocket
- [ ] **Timestamp on git reads** — show "refreshed 3 min ago" on each card

**Deliverable:** KaiView v2 — stable, SQLite-backed, session-aware

---

### Chorus — Core Engine

> Goal: Get one prompt to 4 AIs simultaneously and collect responses.

- [ ] **Project structure**
  - `main.py` — FastAPI entry point
  - `chorus/platforms/` — one file per AI platform
  - `chorus/browser.py` — Playwright session manager
  - `chorus/websocket.py` — live progress streaming
  - `frontend/index.html` — prompt UI + progress view
- [ ] **Playwright session manager**
  - Persistent browser profiles per platform (stored in `profiles/`)
  - First-run login flow per platform
  - Session health check on startup
- [ ] **4 AI platforms**
  - `gemini.py` — Google Gemini
  - `claude.py` — Claude (claude.ai)
  - `chatgpt.py` — ChatGPT
  - `perplexity.py` — Perplexity
  - Each: navigate → paste prompt → detect completion → extract response
- [ ] **WebSocket live progress**
  - Per-platform status: `waiting` → `typing` → `done` → `error`
  - Stream partial responses as they arrive
- [ ] **Basic D3.js tree**
  - Center node: prompt
  - 4 branches: one per AI
  - Click branch to expand full response
  - Color-coded per platform

**Deliverable:** Chorus v0.1 — functional, 4 AIs, live progress, basic tree

---

## PHASE 2 — Intelligence

### KaiView — Make It Smart

- [ ] **AI Context Payload**
  - Per-project `ai_config` block: model, context snippet, stack summary, conventions
  - One-click copy to clipboard
  - Edit via modal
- [ ] **Activity sparklines**
  - 7-day commit frequency bar per project card
  - Stored as rolling array in SQLite, updated by background watcher
- [ ] **Dependency scanner**
  - `npm outdated --json` for Node projects
  - `pip list --outdated --format=json` for Python projects
  - Badge on card: "3 outdated packages"
- [ ] **Dev environment launcher**
  - Auto-detect start command per project (`npm run dev`, `python main.py`, `docker-compose up`)
  - One-click launch in new terminal
  - Track running processes, show "Running" badge
- [ ] **Project health score**
  - Computed from: last commit age, dirty state, has README, has tasks, dependency freshness
  - Displayed as score + colour bar on card

**Deliverable:** KaiView v3 — intelligent project health awareness

---

### Chorus — Full Platform + Consensus

- [ ] **All 8 AI platforms**
  - Add: Grok, Microsoft Copilot, DeepSeek, Mistral
  - Handle non-Google auth (Twitter/X for Grok, Microsoft for Copilot)
- [ ] **Google account switcher**
  - UI dropdown to select which Google profile per platform
  - Multiple named profiles per platform
  - Visual indicator showing which account is active
- [ ] **Consensus engine**
  - TF-IDF keyword extraction per response
  - Theme clustering across responses
  - Consensus score per theme: Full (4/4) → Majority (3/4) → Split (2/4) → Unique
  - Categories: All agree / Most agree / Split / Unique insight
- [ ] **Enhanced D3 tree**
  - Consensus layer at bottom — themes with agreement badges
  - Hover to highlight matching points across branches
  - Animate response arrival in real time
  - Zoom + pan

**Deliverable:** Chorus v0.5 — all 8 AIs, account switching, consensus working

---

## PHASE 3 — Power Features

### KaiView — Power User

- [ ] **Command palette** (Ctrl+K)
  - Fuzzy search: open project, change status, launch dev server, open GitHub
  - Backend `/api/commands` endpoint
- [ ] **Cross-project code search**
  - Search across all project files using `ripgrep`
  - Results grouped by project
  - Click result → open file in VS Code at line number
- [ ] **Links per project**
  - Store: GitHub URL, live URL, docs URL, deploy URL
  - One-click open from card
- [ ] **Kanban view**
  - Toggle between grid and board (columns = status)
  - Drag cards between columns to update status
- [ ] **AI session log**
  - Log AI interactions per project: date, model, topic, outcome
  - Searchable history: "what did I ask about auth last month?"
- [ ] **Project journal**
  - Timestamped notes log per project
  - Not just a single notes field — append-only dev diary

**Deliverable:** KaiView v4 — power user ready

---

### Chorus — Polish

- [ ] **Prompt history**
  - Store all past prompts + responses in SQLite
  - Browse, re-run, compare old vs new responses
- [ ] **Export**
  - Export full session as Markdown
  - Export flowchart as PNG/SVG
  - Export consensus summary as PDF
- [ ] **Prompt templates**
  - Built-in templates: code review, architecture advice, debugging, brainstorm
  - Save custom templates
- [ ] **Response diff view**
  - Side-by-side comparison of any two AI responses
  - Highlighted differences

**Deliverable:** Chorus v1.0 — launch-ready

---

## PHASE 4 — Launch

### KaiView — Open Source Launch

- [ ] **CONTRIBUTING.md** — how to add new stack detectors, AI platforms
- [ ] **Demo GIF** for README
- [ ] **One-command install** — `pip install kaiview` or launch script
- [ ] **Multi-directory support** — scan more than one root folder
- [ ] **localhost auth token** — basic security for the local server
- [ ] **GitHub Actions CI** — lint + basic tests on push
- [ ] **v1.0.0 release tag**

---

### Chorus — Open Source Launch

- [ ] **CONTRIBUTING.md** — how to add new AI platforms
- [ ] **Platform guide** — how to add any new AI site in < 50 lines
- [ ] **Demo GIF** for README
- [ ] **One-command install** — `pip install chorus` or `npx chorus`
- [ ] **GitHub Actions CI**
- [ ] **v1.0.0 release tag**

---

## Parallel Build Schedule

```
SESSION 1 ── KaiView: SQLite migration
             Chorus:  Project structure + Playwright setup

SESSION 2 ── KaiView: Resume / Park system
             Chorus:  First 2 platforms (Gemini + ChatGPT)

SESSION 3 ── KaiView: 3-lens view + staleness score
             Chorus:  Last 2 platforms (Claude + Perplexity) + WebSocket

SESSION 4 ── KaiView: Background git watcher + WebSocket
             Chorus:  Basic D3.js tree

             ── PHASE 1 COMPLETE ──

SESSION 5 ── KaiView: AI Context Payload + sparklines
             Chorus:  4 more platforms (Grok, Copilot, DeepSeek, Mistral)

SESSION 6 ── KaiView: Dependency scanner + health score
             Chorus:  Google account switcher

SESSION 7 ── KaiView: Dev environment launcher
             Chorus:  Consensus engine

SESSION 8 ── KaiView: Enhanced UI polish
             Chorus:  Enhanced D3 tree + animations

             ── PHASE 2 COMPLETE ──

SESSION 9  ── KaiView: Command palette
              Chorus:  Prompt history + export

SESSION 10 ── KaiView: Cross-project search + Kanban
              Chorus:  Templates + diff view

             ── PHASE 3 COMPLETE ──

SESSION 11 ── KaiView: Launch prep
              Chorus:  Launch prep

             ── v1.0.0 BOTH PROJECTS ──
```

---

## Tech Decisions Locked

| Decision | KaiView | Chorus |
|---|---|---|
| Storage | SQLite (aiosqlite) | SQLite (aiosqlite) |
| Backend | FastAPI + uvicorn | FastAPI + uvicorn |
| Frontend | Vanilla JS | Vanilla JS + D3.js |
| Realtime | WebSocket | WebSocket |
| Browser automation | — | Playwright (Chromium) |
| Consensus | — | scikit-learn TF-IDF + NLTK |
| Port | 3737 | 4747 |
| License | MIT | MIT |

---

## Definition of Done (per phase)

- [ ] All items in phase checklist complete
- [ ] No critical bugs
- [ ] README updated
- [ ] Committed and pushed to GitHub
- [ ] Phase tag created (e.g. `v0.1-phase1`)
