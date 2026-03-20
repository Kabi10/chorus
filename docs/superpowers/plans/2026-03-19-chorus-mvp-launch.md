# Chorus MVP Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship three launch-prep improvements — PyPI packaging as `chorus-ai`, a first-load explainer card, and a demo GIF — to prepare Chorus for Product Hunt.

**Architecture:** All changes are isolated: `pyproject.toml` + `requirements.txt` for packaging, a single JS/CSS block appended to `index.html` for the overlay, and a browser-recorded GIF saved to `docs/`. No new Python files, no new dependencies beyond what's already in use.

**Tech Stack:** Python packaging (setuptools, build, twine), Vanilla JS + CSS (overlay), Playwright/Chrome browser automation (GIF recording)

---

## File Map

| File | Change |
|------|--------|
| `pyproject.toml` | Rename to `chorus-ai`, add `websockets`, classifiers, URLs |
| `requirements.txt` | Sync with `pyproject.toml`: add `aiohttp`, `websockets`, fix `uvicorn[standard]` |
| `chorus/frontend/index.html` | Append explainer card overlay (CSS + JS block before `</body>`) |
| `docs/demo.gif` | New file — recorded GIF of live Chorus session |
| `README.md` | Swap static screenshot for `demo.gif`, update install instructions |

---

## Task 0: Create Feature Branch

- [ ] **Step 1: Create and switch to the feature branch**

  ```bash
  cd /c/dev/chorus
  git checkout -b launch/mvp-improvements
  ```

  All commits in Tasks 1–3 go on this branch. Task 4 (PyPI publish) happens after the branch is merged.

---

## Task 1: PyPI Packaging — `pyproject.toml` + `requirements.txt`

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

- [ ] **Step 1: Update `pyproject.toml`**

  Open `pyproject.toml`. Make these changes:

  ```toml
  [project]
  name = "chorus-ai"                          # was "chorus"
  version = "1.0.0"
  description = "Query multiple AI platforms simultaneously"
  readme = "README.md"
  license = {text = "MIT"}
  requires-python = ">=3.10"
  keywords = ["ai", "llm", "chatgpt", "claude", "gemini", "multi-ai", "playwright"]
  classifiers = [
      "Development Status :: 4 - Beta",
      "License :: OSI Approved :: MIT License",
      "Programming Language :: Python :: 3",
      "Programming Language :: Python :: 3.10",
      "Programming Language :: Python :: 3.11",
      "Programming Language :: Python :: 3.12",
      "Topic :: Scientific/Engineering :: Artificial Intelligence",
  ]
  dependencies = [
      "fastapi>=0.100.0",
      "uvicorn[standard]>=0.23.0",
      "playwright>=1.40",
      "aiohttp>=3.9.0",
      "httpx>=0.25.0",
      "pydantic>=2.0.0",
      "websockets>=11.0",
  ]

  [project.urls]
  Homepage = "https://github.com/Kabi10/chorus"
  Source = "https://github.com/Kabi10/chorus"
  "Bug Tracker" = "https://github.com/Kabi10/chorus/issues"
  ```

  The `[build-system]` and `[project.scripts]` sections stay unchanged.

- [ ] **Step 2: Sync `requirements.txt`**

  Replace the full content of `requirements.txt` with:

  ```
  fastapi>=0.100.0
  uvicorn[standard]>=0.23.0
  playwright>=1.40.0
  aiohttp>=3.9.0
  httpx>=0.25.0
  pydantic>=2.0.0
  websockets>=11.0
  ```

  (Added `aiohttp`, `websockets`; changed `uvicorn` → `uvicorn[standard]` to match `pyproject.toml`)

- [ ] **Step 3: Run existing tests to verify nothing broke**

  ```bash
  cd /c/dev/chorus
  pytest tests/test_packaging.py -v
  ```

  Expected output — all 4 tests pass:
  ```
  PASSED tests/test_packaging.py::test_main_is_importable_and_callable
  PASSED tests/test_packaging.py::test_check_playwright_exits_when_chromium_missing
  PASSED tests/test_packaging.py::test_version_exported
  PASSED tests/test_packaging.py::test_frontend_html_accessible_from_package
  ```

  If `test_version_exported` fails: check `chorus/__init__.py` exports `__version__ = "1.0.0"`.

- [ ] **Step 4: Run full test suite**

  ```bash
  pytest --tb=short -q
  ```

  Expected: all tests pass. If failures exist, fix before continuing.

- [ ] **Step 5: Commit**

  ```bash
  git add pyproject.toml requirements.txt
  git commit -m "feat: rename PyPI package to chorus-ai, sync requirements.txt"
  ```

---

## Task 2: Explainer Card Overlay

**Files:**
- Modify: `chorus/frontend/index.html` (append before `</body>`)

The overlay must only show when (1) onboarding is complete per `/api/onboarding/state` and (2) `chorus_seen` is absent from `localStorage`. It must never conflict with the existing onboarding wizard (`ob-overlay`, z-index 950).

- [ ] **Step 1: Add the CSS and HTML**

  In `chorus/frontend/index.html`, find the closing `</body>` tag (line 1413) and insert the following block immediately before it:

  ```html
  <!-- ── Explainer card overlay ── -->
  <style>
  #explainer-overlay{
    position:fixed;inset:0;z-index:9999;
    background:rgba(11,11,16,0.96);
    display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;
    opacity:0;pointer-events:none;transition:opacity .4s ease-out;
  }
  #explainer-overlay.visible{opacity:1;pointer-events:auto}
  #explainer-overlay.hiding{opacity:0;transition:opacity .6s ease-in}
  #explainer-headline{
    font-size:28px;font-weight:700;color:var(--text);
    max-width:600px;text-align:center;line-height:1.3;
  }
  #explainer-sub{
    font-size:14px;color:var(--dim);text-align:center;
  }
  </style>
  <div id="explainer-overlay">
    <div id="explainer-headline">Ask all AI models at once. See where they agree.</div>
    <div id="explainer-sub">8 AIs. One prompt. Zero API keys.</div>
  </div>
  ```

- [ ] **Step 2: Add the JS**

  Immediately after the HTML block above (still before `</body>`), add:

  ```html
  <script>
  (function(){
    if (localStorage.getItem('chorus_seen')) return;

    async function maybeShowExplainer() {
      try {
        const r = await fetch('/api/onboarding/state');
        if (!r.ok) return;
        const state = await r.json();
        const onboardingComplete = Object.values(state).some(v => v.status === 'completed');
        if (!onboardingComplete) return;
      } catch(e) { return; }

      const el = document.getElementById('explainer-overlay');
      // Fade in
      el.classList.add('visible');

      function dismiss() {
        el.classList.add('hiding');
        el.classList.remove('visible');
        setTimeout(() => { el.remove(); }, 600);
        localStorage.setItem('chorus_seen', '1');
        document.removeEventListener('keydown', dismiss);
        document.removeEventListener('click', dismiss);
      }

      // Dismiss on interaction
      document.addEventListener('keydown', dismiss, {once: true});
      document.addEventListener('click', dismiss, {once: true});

      // Auto-dismiss: 400ms fade-in + 3000ms hold = 3400ms, then fade-out 600ms, remove at 4000ms
      setTimeout(() => {
        if (localStorage.getItem('chorus_seen')) return; // already dismissed
        dismiss();
      }, 3400);
    }

    window.addEventListener('load', maybeShowExplainer);
  })();
  </script>
  ```

- [ ] **Step 3: Verify the HTML is valid**

  ```bash
  grep -c "</body>" /c/dev/chorus/chorus/frontend/index.html
  ```

  Expected: `1` (only one closing body tag — confirms no duplication).

- [ ] **Step 4: Run packaging tests to confirm HTML is still valid package data**

  ```bash
  pytest tests/test_packaging.py::test_frontend_html_accessible_from_package -v
  ```

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add chorus/frontend/index.html
  git commit -m "feat: add first-load explainer card overlay"
  ```

---

## Task 3: Demo GIF Recording

**Files:**
- Create: `docs/demo.gif`
- Modify: `README.md`

**Prerequisites before this task:**
- Chorus must be running: `chorus` (starts server at localhost:4747)
- At least 3–4 platforms must be logged in via the onboarding wizard in Chorus's own Chrome profile (`~/.chorus/profile/`). Recommended: ChatGPT, Claude, Gemini, DeepSeek.
- Confirm the app loads at `localhost:4747` before recording.

- [ ] **Step 1: Start Chorus**

  In a separate terminal:
  ```bash
  cd /c/dev/chorus
  chorus
  ```

  Wait for: `Uvicorn running on http://127.0.0.1:4747`

- [ ] **Step 2: Record the GIF using browser automation**

  Use the `mcp__claude-in-chrome__gif_creator` tool to record a session. Script:
  1. Open `http://localhost:4747`
  2. Wait for the app to fully load (progress cards visible)
  3. Click the prompt textarea
  4. Type: `What is the best programming language to learn in 2025?`
  5. Select all logged-in platforms (unlogged platforms will error gracefully — that's fine)
  6. Click Send
  7. Let all responses stream in (watch progress cards)
  8. Switch to "Cards" view tab to show side-by-side responses
  9. Stop recording

  Target: ~20–25 seconds, 1280×720, under 5MB.

- [ ] **Step 3: Save and verify GIF size**

  Save output to `docs/demo.gif`. Then check size:
  ```bash
  ls -lh /c/dev/chorus/docs/demo.gif
  ```

  Expected: under 5MB. If larger, re-record at lower resolution or reduce frame rate.

- [ ] **Step 4: Update README.md**

  In `README.md`, find line 5:
  ```markdown
  ![Chorus](docs/screenshot.png)
  ```

  Replace with:
  ```markdown
  ![Chorus demo](docs/demo.gif)
  ```

  Also update the Quick Start section — change:
  ```bash
  # 1. Clone
  git clone https://github.com/Kabi10/chorus.git
  cd chorus

  # 2. Install Python dependencies
  pip install -e .
  ```

  To:
  ```bash
  # 1. Install
  pip install chorus-ai

  # 2. Install Playwright browser
  playwright install chromium

  # 3. Run
  chorus
  ```

  Keep the rest of Quick Start unchanged (the "Open http://localhost:4747" and onboarding note).

- [ ] **Step 5: Commit**

  ```bash
  git add docs/demo.gif README.md
  git commit -m "feat: add demo GIF, update README with pip install chorus-ai"
  ```

---

## Task 4: Publish to PyPI

**Prerequisites:** PyPI account with API token. Configure `~/.pypirc`:
```ini
[pypi]
username = __token__
password = pypi-<your-token-here>
```

Or pass credentials inline to `twine`.

- [ ] **Step 1: Install build tools if needed**

  ```bash
  pip install build twine
  ```

- [ ] **Step 2: Clean any previous build artifacts**

  ```bash
  rm -rf /c/dev/chorus/dist/ /c/dev/chorus/*.egg-info
  ```

  On Windows bash: `rm -rf dist/ chorus.egg-info/`

- [ ] **Step 3: Build the distribution**

  ```bash
  cd /c/dev/chorus
  python -m build
  ```

  Expected output ends with:
  ```
  Successfully built chorus_ai-1.0.0.tar.gz and chorus_ai-1.0.0-py3-none-any.whl
  ```

  Confirm the dist filenames contain `chorus_ai` (not `chorus`).

- [ ] **Step 4: Check the distribution before uploading**

  ```bash
  twine check dist/*
  ```

  Expected: `PASSED chorus_ai-1.0.0.tar.gz` and `PASSED chorus_ai-1.0.0-py3-none-any.whl`. Fix any warnings before uploading.

- [ ] **Step 5: Upload to PyPI**

  ```bash
  twine upload dist/*
  ```

  Expected: upload succeeds, prints URL: `https://pypi.org/project/chorus-ai/1.0.0/`

  > **If upload fails with "File already exists":** bump the version to `1.0.1` in both `pyproject.toml` and `chorus/__init__.py`, re-build, and re-upload.

- [ ] **Step 6: Verify install from PyPI**

  In a fresh terminal (or venv):
  ```bash
  pip install chorus-ai
  chorus --help
  ```

  Expected: installs cleanly, `chorus` command available.

- [ ] **Step 7: Tag the release**

  ```bash
  git tag v1.0.0
  git push origin master --tags
  ```

---

## Execution Order

```
Task 1 (pyproject + requirements)
  └─→ Task 2 (explainer card)
        └─→ Task 3 (GIF — requires Chorus running)
              └─→ Task 4 (PyPI publish — must be after all commits)
```
