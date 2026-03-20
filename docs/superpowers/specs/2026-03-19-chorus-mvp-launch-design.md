# Chorus MVP Launch — Design Spec
> Date: 2026-03-19

## Overview

Three targeted improvements to ship Chorus for a Product Hunt launch:

1. **PyPI packaging** — publish as `chorus-ai` so users can `pip install chorus-ai`
2. **Explainer card** — first-load hero overlay with the product tagline
3. **Demo GIF** — animated recording of a real Chorus session for README and Product Hunt

---

## 1. PyPI Packaging (`chorus-ai`)

### Problem
`chorus` is already taken on PyPI (unrelated package, v0.9.0). The project's `pyproject.toml` currently declares `name = "chorus"`, which would conflict on upload.

### Changes to `pyproject.toml`
- `name = "chorus-ai"`
- Add `aiohttp>=3.9.0` to dependencies (used in codebase, missing from manifest)
- Add `keywords` array: `["ai", "llm", "chatgpt", "claude", "gemini", "multi-ai", "playwright"]`
- Add `classifiers`: Python 3.10+, MIT License, Development Status :: 4 - Beta, Topic :: Scientific/Engineering :: Artificial Intelligence
- Add `[project.urls]`: Homepage (GitHub), Source (GitHub)

### CLI entrypoint
The `chorus` command stays unchanged — only the PyPI package name changes. Users run:
```bash
pip install chorus-ai
chorus
```

### Publish steps (manual)
```bash
python -m build
twine upload dist/*
```

Requires a PyPI account and API token in `~/.pypirc` or passed via `--username`/`--password`.

---

## 2. Explainer Card (Hero Overlay)

### Behaviour
- Renders on first load as a full-screen overlay above the main UI
- Auto-dismisses after **3 seconds**
- Also dismisses immediately on any click or keypress
- After first dismissal, `localStorage.setItem('chorus_seen', '1')` is set — never shown again

### Copy
- **Headline:** `Ask all AI models at once. See where they agree.`
- **Sub-line:** `8 AIs. One prompt. Zero API keys.`

### Style
- Background: `rgba(11, 11, 16, 0.96)` — matches `--bg`, near-opaque
- Headline: 28px, weight 700, white (`--text`)
- Sub-line: 14px, `--dim` color
- Animation: fade in 0.4s ease-out → hold → fade out 0.6s ease-in
- `position: fixed`, `z-index: 9999`, centered via flexbox

### Implementation
Pure CSS + JS injected into `chorus/frontend/index.html`. No new files, no dependencies.

---

## 3. Demo GIF

### Recording plan
1. Start Chorus: `chorus` (background process)
2. Open `localhost:4747` in Chrome via browser automation
3. Script the interaction:
   - Type prompt: `"What is the best programming language to learn in 2025?"`
   - Select all available platforms
   - Click Send
   - Watch live progress cards stream in
   - Switch to Cards view showing responses
4. Record with `gif_creator` tool
5. Duration: ~20–25 seconds, loops cleanly

### Prerequisites
- Run `chorus` once before recording and log into at least 3–4 platforms via the onboarding wizard (`~/.chorus/profile/` is the persistent profile)
- Recommended: ChatGPT, Claude, Gemini, DeepSeek

### Output
- Save to `docs/demo.gif`
- Update `README.md`: replace `![Chorus](docs/screenshot.png)` → `![Chorus demo](docs/demo.gif)`

---

## Delivery Strategy

Single branch `launch/mvp-improvements` — all three items bundled as one PR.

**Order of implementation:**
1. `pyproject.toml` changes (2 min)
2. Explainer card in `index.html` (15 min)
3. Demo GIF recording (requires Chorus running + platform logins)
4. README update
5. Build + publish to PyPI
