# Changelog

All notable changes to Chorus are documented here.

---

## [1.0.0] — 2026-03-20

Initial public release.

### Platforms

- ChatGPT (chat.openai.com / chatgpt.com)
- Claude (claude.ai)
- Gemini (gemini.google.com)
- Grok (x.com/i/grok)
- Perplexity (perplexity.ai)
- Microsoft Copilot (copilot.microsoft.com)
- DeepSeek (chat.deepseek.com)
- Mistral Le Chat (chat.mistral.ai)

### Features

- **Parallel querying** — all selected AIs receive the prompt simultaneously via `asyncio.gather`
- **Live progress** — WebSocket streams each AI's status in real time (queued → typing → done / error)
- **Tree view** — D3.js horizontal tree; click any platform node to read its full response in a modal
- **Cards view** — response cards with markdown rendering, word count, copy, and expand/collapse
- **Consensus view** — server-side Jaccard similarity analysis: shared themes, consensus keywords, pairwise similarity heatmap, per-platform response stats
- **Diff view** — sentence-level diff; sentences unique to a single AI are highlighted
- **Onboarding wizard** — first-run flow that opens a Chromium window for each platform login; sessions saved locally in `~/.chorus/profiles/`
- **Account switcher** — multiple named profiles per platform; switch mid-session
- **Follow-up prompts** — send a second prompt to the same browser pages (preserving conversation context)
- **Error recovery** — per-platform Retry button (up to 3 attempts); Re-login button when auth expires
- **Prompt templates** — 5 built-in developer-focused templates
- **Session history** — last 100 sessions persisted to `~/.chorus/chorus_history.json`
- **Markdown export** — download any session as a formatted `.md` file
- **No API keys** — uses Playwright-driven Chromium with your existing browser sessions

### Stack

- Python 3.10+, FastAPI, uvicorn, asyncio
- Playwright (Chromium, persistent contexts, CDP)
- Vanilla HTML/CSS/JS, D3.js v7
- WebSockets for live updates

### Known Limitations

- Requires Chromium (installed via `playwright install chromium`)
- 8 concurrent browser contexts use ~1–2 GB RAM when all platforms are active
- Platform CSS selectors are maintained manually; they may break when an AI platform redesigns its UI — see [CONTRIBUTING.md](CONTRIBUTING.md) for how to fix and submit a selector update
- Rate limits on free-tier accounts can cause intermittent failures; the Retry button handles most cases
- Follow-up prompts depend on the platform keeping the conversation open — some platforms expire sessions after inactivity
