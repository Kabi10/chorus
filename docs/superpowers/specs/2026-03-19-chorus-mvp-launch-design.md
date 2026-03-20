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
- `name = "chorus-ai"` (was `"chorus"`)
- Add `websockets>=11.0` to dependencies — it's in `requirements.txt` but missing from `pyproject.toml`; `websocket_manager.py` uses it
- Add `keywords` array: `["ai", "llm", "chatgpt", "claude", "gemini", "multi-ai", "playwright"]`
- Add `classifiers`: Python 3.10+, MIT License, Development Status :: 4 - Beta, Topic :: Scientific/Engineering :: Artificial Intelligence
- Add `[project.urls]`: Homepage (GitHub), Source (GitHub), Bug Tracker (GitHub Issues)

### Sync `requirements.txt`
Also update `requirements.txt` to match `pyproject.toml`:
- Add `aiohttp>=3.9.0` (used in `browser.py`, present in `pyproject.toml` but missing from `requirements.txt`)
- Change `uvicorn>=0.23.0` → `uvicorn[standard]>=0.23.0` to match `pyproject.toml`
- Add `websockets>=11.0` (same change as `pyproject.toml`)

### Import namespace vs. install name
The Python import namespace stays `chorus` regardless of the PyPI distribution name `chorus-ai`. `import chorus` works; `import chorus-ai` does not exist. The test suite in `tests/test_packaging.py` uses `importlib.resources.files("chorus")` which is correct and unaffected by the rename.

### Version
Keep at `1.0.0` for the initial PyPI publish. PyPI does not allow re-uploading the same version — if a re-publish is needed after fixes, bump to `1.0.1`.

### CLI entrypoint
The `chorus` command stays unchanged — only the PyPI package name changes. Users install and run:
```bash
pip install chorus-ai
playwright install chromium
chorus
```

### Publish steps
```bash
pip install build twine   # prereqs if not already installed
python -m build
twine upload dist/*
```
Requires a PyPI account and API token configured in `~/.pypirc`.

### Before publishing
Run `pytest` and confirm all tests pass. `tests/test_packaging.py` includes version and frontend accessibility checks that must pass.

---

## 2. Explainer Card (Hero Overlay)

### Behaviour
- Renders on first load as a full-screen overlay above the main UI
- Only shown when **both** conditions are true:
  1. Onboarding is complete — determined by calling `/api/onboarding/state` and checking that at least one platform has `status === 'completed'` (same check the existing `index.html` uses at line 1404 via `needsSetup`)
  2. `chorus_seen` is absent from localStorage — meaning the user hasn't dismissed this card before
  - On a fresh install the onboarding wizard takes precedence; the explainer card is for users who have completed setup at least once.
- Dismiss timing sequence:
  1. Fade in: 0.4s ease-out (starts immediately)
  2. Hold: 3.0s (begins after fade-in completes)
  3. Fade out: 0.6s ease-in (triggered at t=3.4s)
  4. DOM removal: at t=4.0s (after fade-out finishes)
  - Total elapsed: ~4 seconds. `setTimeout` must account for the full sequence, not just the hold time.
- Also dismisses immediately on any click or keypress (skips to fade-out)
- After first dismissal: `localStorage.setItem('chorus_seen', '1')` — overlay never shown again
- If localStorage is cleared: overlay reappears harmlessly on next load (intentional)

### Copy
- **Headline:** `Ask all AI models at once. See where they agree.`
- **Sub-line:** `8 AIs. One prompt. Zero API keys.`

### Style
- Background: `rgba(11, 11, 16, 0.96)` — matches `--bg`, near-opaque
- Headline: 28px, weight 700, `--text` color, `max-width: 600px`, `text-align: center`
- Sub-line: 14px, `--dim` color
- `position: fixed`, `inset: 0`, `z-index: 9999`, centered via flexbox

### Implementation
Pure CSS + JS injected into `chorus/frontend/index.html`. No new files, no dependencies.

---

## 3. Demo GIF

### Recording plan
1. Pre-warm the Chorus profile: run `chorus` once and verify sessions are alive (check platform status in onboarding). The Playwright profile lives at `~/.chorus/profile/` — this is NOT the system Chrome profile.
2. Log into at least ChatGPT, Claude, Gemini, and one more via the onboarding wizard before recording
3. Start Chorus: `chorus` (background process)
4. Open `localhost:4747` in Chrome via browser automation
5. Script the interaction:
   - Type prompt: `"What is the best programming language to learn in 2025?"`
   - Select all available platforms
   - Click Send
   - Watch live progress cards stream in
   - Switch to Cards view showing responses
6. Record with `gif_creator` tool
7. Duration: ~20–25 seconds, loops cleanly

### GIF constraints
- Target resolution: **1280×720** (crop browser chrome if needed)
- File size ceiling: **5MB**. If the output exceeds this, reduce colour depth or frame rate. For Product Hunt use an MP4/WebP conversion; the GIF is for the GitHub README only.

### Output
- Save to `docs/demo.gif`
- Update `README.md`: replace `![Chorus](docs/screenshot.png)` → `![Chorus demo](docs/demo.gif)`

---

## Delivery Strategy

**Branch:** `launch/mvp-improvements` off `master` (the repo's current default branch).

**Implementation order:**
1. `pyproject.toml` changes
2. Explainer card in `index.html`
3. Run `pytest` — confirm all tests pass
4. Demo GIF recording (requires Chorus running + platform logins pre-warmed)
5. README update
6. Build + publish to PyPI (`python -m build && twine upload dist/*`)
