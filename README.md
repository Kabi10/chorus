# Chorus

> Send one prompt to every major AI. See where they agree.

![Chorus Logo](logo.png)

**Chorus** is a browser-native multi-AI consultation tool. Write one prompt, send it to ChatGPT, Claude, Gemini, Grok, Perplexity, DeepSeek, Mistral, and Copilot simultaneously — **no API keys required**. Uses your existing logged-in browser sessions and collects all responses into a D3 flowchart with consensus analysis, sentence-level diff, and Markdown export.

---

## Why Chorus?

| Other tools | Chorus |
|---|---|
| Require expensive API keys | Zero API keys — uses your browser sessions |
| Compare 2-3 AIs | 8 AIs simultaneously |
| Raw text side-by-side | D3 tree + Consensus + Diff views |
| No account switching | Per-platform profile manager built in |
| Responses lost on refresh | Full history persisted to disk |
| Closed source / paid | Fully open source |

---

## Supported Platforms

| Platform | URL used |
|---|---|
| 🟢 ChatGPT | chatgpt.com |
| 🟣 Claude | claude.ai/new |
| 🌀 Gemini | gemini.google.com |
| ✕ Grok | x.com/i/grok |
| 🔭 Perplexity | perplexity.ai |
| 🪟 Copilot | copilot.microsoft.com |
| 🔵 DeepSeek | chat.deepseek.com |
| 🔶 Mistral | chat.mistral.ai |

---

## Features

| | |
|---|---|
| ⚡ **Zero API keys** | Playwright drives your real browser — no tokens, no billing |
| 🔀 **Parallel querying** | All AIs receive the prompt simultaneously via `asyncio.gather` |
| 📡 **Live progress** | WebSocket streams each AI's status (queued → typing → done) |
| 🌳 **Tree view** | D3.js radial tree — click any node to read the full response |
| 📋 **Cards view** | Side-by-side response cards with copy button |
| 🎯 **Consensus view** | Keyword agreement analysis — what all AIs agree on vs. split opinions |
| 🔍 **Diff view** | Sentence-level diff — unique insights per AI highlighted in blue |
| 🏷️ **Prompt templates** | 5 built-in templates to get started quickly |
| 📂 **Persistent history** | All sessions saved to `chorus_history.json` — reload anytime |
| ↓ **Markdown export** | Download any session as a formatted `.md` file |
| ⚙️ **Account switcher** | Multiple Google/platform accounts per AI, switch with one click |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Kabi10/chorus.git
cd chorus

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Playwright browser
playwright install chromium

# 4. Run
python main.py
```

Open **http://localhost:4747**

> **First run:** Chorus opens a browser window per selected AI. Log in once — sessions are saved in `chorus/profiles/` and reused automatically.

---

## Adding a New Account (e.g. work Google for Gemini)

1. Click the **⚙** icon next to any platform in the Send panel
2. Click **+ Add account** and enter a name (e.g. `work`)
3. Chorus opens a fresh browser window — log in as your work account
4. Close the login window — the profile is saved
5. Select it from the dropdown next time you send

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/platforms` | List platforms + metadata |
| `GET` | `/api/platforms/{p}/profiles` | List saved profiles |
| `POST` | `/api/platforms/{p}/profiles/{name}` | Create profile + open for login |
| `POST` | `/api/query` | Start a query session |
| `GET` | `/api/sessions/{id}` | Session status + responses |
| `GET` | `/api/history` | Saved session history |
| `DELETE` | `/api/history/{id}` | Remove a history item |
| `GET` | `/api/export/{id}` | Download session as Markdown |
| `WS` | `/ws` | Live platform status updates |

---

## Project Structure

```
chorus/
  main.py                    # FastAPI app + session orchestration
  requirements.txt
  chorus_history.json        # Persisted session history
  chorus/
    browser.py               # Playwright BrowserManager (persistent profiles)
    websocket_manager.py     # WebSocket broadcast
    platforms/
      base.py                # BaseAI ABC
      gemini.py
      chatgpt.py
      claude.py
      perplexity.py
      grok.py
      copilot.py
      deepseek.py
      mistral.py
  frontend/
    index.html               # Full SPA (D3, WebSocket, consensus engine)
  profiles/                  # Browser profiles (gitignored)
```

---

## Adding a New AI Platform

1. Create `chorus/platforms/myai.py` extending `BaseAI`
2. Implement `submit_prompt()` and `wait_for_response()`
3. Register in `main.py` `PLATFORMS` and `PLATFORM_META` dicts
4. That's it — the frontend picks it up automatically

---

## Stack

- **Backend:** Python 3.10+, FastAPI, uvicorn
- **Browser automation:** Playwright (Chromium, persistent contexts)
- **Frontend:** Vanilla HTML/CSS/JS, D3.js v7
- **Consensus:** Client-side keyword overlap (no server ML needed)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome — especially new platform connectors, better selectors for existing platforms, and UI improvements.

## License

MIT © [Kabi10](https://github.com/Kabi10)
