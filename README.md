# Chorus

> Send one prompt to every major AI. See where they agree.

![Chorus Logo](logo.png)

## What is Chorus?

Chorus is a browser-native multi-AI consultation tool. Write one prompt, send it to ChatGPT, Claude, Gemini, Grok, Perplexity, DeepSeek, Mistral, and Copilot simultaneously — no API keys required. It uses your existing browser sessions (where you're already logged in) and collects all responses into a beautiful flowchart with consensus analysis.

## Why Chorus?

| Other tools | Chorus |
|---|---|
| Require expensive API keys | Zero API keys — uses your browser sessions |
| Compare 2-3 AIs | Supports 8+ AIs simultaneously |
| Show raw text side-by-side | D3.js flowchart tree + consensus layer |
| No account switching | Google OAuth profile management built in |
| Closed source or paid | Fully open source |

## Supported AI Platforms

- ChatGPT (OpenAI)
- Claude (Anthropic)
- Gemini (Google)
- Grok (xAI)
- Perplexity
- Microsoft Copilot
- DeepSeek
- Mistral (Le Chat)

## Features

- **Zero API keys** — runs entirely through browser automation
- **Parallel querying** — all AIs receive the prompt simultaneously
- **Live progress** — watch each AI respond in real time via WebSocket
- **Flowchart visualization** — D3.js tree showing all responses branching from your prompt
- **Consensus engine** — automatically identifies what all AIs agreed on, what was split, and unique insights
- **Google account switcher** — use different Google accounts per AI platform
- **Persistent sessions** — log in once per platform, stay logged in forever

## Getting Started

### Requirements

- Python 3.10+
- Chrome or Chromium browser

### Install

```bash
git clone https://github.com/Kabi10/chorus.git
cd chorus
pip install -r requirements.txt
playwright install chromium
```

### Run

```bash
python main.py
```

Open [http://localhost:4747](http://localhost:4747)

On first run, Chorus will open browser windows for each AI platform so you can log in. After that, sessions are saved automatically.

## Roadmap

- [ ] Core: 4 AI platforms (Gemini, Claude, ChatGPT, Perplexity)
- [ ] WebSocket live progress
- [ ] Basic response collection
- [ ] D3.js flowchart tree
- [ ] All 8 AI platforms
- [ ] Google account switcher UI
- [ ] Consensus engine (TF-IDF + theme extraction)
- [ ] Export responses as PDF / Markdown
- [ ] Prompt history
- [ ] Template library

## Stack

- **Backend:** Python, FastAPI, Playwright
- **Frontend:** Vanilla HTML/CSS/JS, D3.js
- **Browser automation:** Playwright (Chromium)
- **Consensus:** scikit-learn (TF-IDF), NLTK

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT © [Kabi10](https://github.com/Kabi10)
