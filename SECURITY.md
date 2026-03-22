# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅ Yes     |

## How Chorus Handles Your Data

Chorus is designed to run **entirely on your local machine**:

- **No data leaves your machine** through Chorus itself. Prompts are sent directly from your browser to each AI platform — Chorus is just the orchestrator.
- **Browser sessions** are stored in `~/.chorus/profiles/` using Playwright persistent contexts. These contain your login cookies for each AI platform. They are never transmitted anywhere.
- **Session history** is stored in `~/.chorus/chorus_history.json`. It contains your prompts and AI responses, stored locally only.
- **No telemetry.** Chorus collects nothing.
- The local server binds to `127.0.0.1:4747` only — it is not accessible from other machines on your network.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, email the maintainer directly:

**security contact:** open a [GitHub Security Advisory](https://github.com/Kabi10/chorus/security/advisories/new) (private disclosure)

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix if you have one

You can expect an acknowledgement within 48 hours and a fix or mitigation plan within 7 days for confirmed vulnerabilities.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Local server (`127.0.0.1:4747`) vulnerabilities | Issues with third-party AI platforms themselves |
| XSS in the frontend rendering AI responses | Rate limiting / ToS enforcement by platforms |
| Path traversal in file storage (`~/.chorus/`) | Social engineering |
| Dependency vulnerabilities with known CVEs | Theoretical issues with no practical exploit |

## Dependency Security

Chorus uses a minimal dependency set (FastAPI, uvicorn, Playwright, aiohttp, httpx, pydantic, websockets). If you discover a CVE in any of these that affects Chorus, please report it so we can update the pinned versions.
