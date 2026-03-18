import asyncio
import importlib.resources
import json
import json as _json
import sys
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from playwright.sync_api import sync_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeout

from chorus.browser import manager as browser_manager
from chorus.websocket_manager import ws_manager
from chorus import onboarding as _onboarding
from chorus.platforms.gemini import Gemini
from chorus.platforms.chatgpt import ChatGPT
from chorus.platforms.claude import Claude
from chorus.platforms.perplexity import Perplexity
from chorus.platforms.grok import Grok
from chorus.platforms.copilot import Copilot
from chorus.platforms.deepseek import DeepSeek
from chorus.platforms.mistral import Mistral

_UNIVERSAL_RATE_SIGNALS = [
    "too many requests", "rate limit", "try again later", "quota exceeded",
]


def _classify_error(platform: str, exc: Exception, page_text: str = "") -> tuple[str, str]:
    """Map an exception + page content to (error_code, human_message)."""
    page_lower = page_text.lower()

    # Check rate limit signals (platform-specific + universal)
    import importlib.resources as _ir, json as _j
    try:
        _sel = _j.loads(_ir.files("chorus").joinpath("selectors.json").read_text())
    except Exception:
        _sel = {}
    signals = list(_sel.get(platform, {}).get("rate_limit_signals", []))
    signals += _UNIVERSAL_RATE_SIGNALS
    if any(s.lower() in page_lower for s in signals):
        platform_name = PLATFORM_META.get(platform, {}).get("name", platform.capitalize())
        return "rate_limited", f"{platform_name} is rate-limiting requests. Wait a moment and retry."

    # asyncio.TimeoutError is a subclass of TimeoutError in Python 3.11+,
    # but a separate class in 3.10. Check both.
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) and not isinstance(exc, PlaywrightTimeout):
        return "timeout", f"{platform.capitalize()} took too long to respond. Try retrying."

    if isinstance(exc, PlaywrightTimeout) and "rate" not in page_lower:
        return "selector_error", (
            f"{platform.capitalize()} UI may have changed. "
            "Check for a platform update in the Chorus repo."
        )

    # Strip Playwright call-log noise — keep only the first line of the message
    raw = str(exc).split("\n")[0].strip()
    platform_name = PLATFORM_META.get(platform, {}).get("name", platform.capitalize())

    if "Target page, context or browser has been closed" in raw:
        return "browser_closed", (
            f"{platform_name}: browser window was closed. Restart Chorus to reconnect."
        )

    return "unknown", f"{platform_name}: {raw[:120]}"


_CHORUS_DIR  = Path.home() / ".chorus"
_CHORUS_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = _CHORUS_DIR / "chorus_history.json"
MAX_HISTORY  = 100
# Read HTML into memory at startup — importlib.resources returns a Traversable, not a real
# filesystem path in installed wheels. Read content directly; never store as Path.
_HTML_CONTENT: str = importlib.resources.files("chorus").joinpath("frontend/index.html").read_text(encoding="utf-8")

PLATFORMS = {
    "gemini":     Gemini,
    "chatgpt":    ChatGPT,
    "claude":     Claude,
    "perplexity": Perplexity,
    "grok":       Grok,
    "copilot":    Copilot,
    "deepseek":   DeepSeek,
    "mistral":    Mistral,
}

_ONBOARDING_FILE: Path   = Path.home() / ".chorus" / "onboarding.json"
_onboarding_pages: dict  = {}  # platform -> Page (in shared context)

PLATFORM_META = {
    "gemini":     {"name": "Gemini",     "color": "#4285F4", "icon": "🌀"},
    "chatgpt":    {"name": "ChatGPT",    "color": "#10a37f", "icon": "🟢"},
    "claude":     {"name": "Claude",     "color": "#d97706", "icon": "🟣"},
    "perplexity": {"name": "Perplexity", "color": "#20b8cd", "icon": "🔭"},
    "grok":       {"name": "Grok",       "color": "#1d9bf0", "icon": "✕"},
    "copilot":    {"name": "Copilot",    "color": "#0078d4", "icon": "🪟"},
    "deepseek":   {"name": "DeepSeek",   "color": "#4d6bfe", "icon": "🔵"},
    "mistral":    {"name": "Mistral",    "color": "#ff7000", "icon": "🔶"},
}

app = FastAPI(title="Chorus")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

active_sessions: dict[str, dict] = {}
prompt_history:  list[dict]      = []


def load_history():
    global prompt_history
    if HISTORY_FILE.exists():
        try:
            prompt_history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            prompt_history = []


def save_history():
    try:
        HISTORY_FILE.write_text(
            json.dumps(prompt_history[-MAX_HISTORY:], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass


class QueryRequest(BaseModel):
    prompt:    str
    platforms: list[str] = list(PLATFORMS.keys())
    profiles:  dict[str, str] = {}

class FollowUpRequest(BaseModel):
    prompt: str


@app.on_event("startup")
async def startup():
    load_history()
    await browser_manager.start()
    print("Chorus running at http://localhost:4747")


@app.on_event("shutdown")
async def shutdown():
    await browser_manager.stop()
    _onboarding_pages.clear()


@app.get("/", response_class=HTMLResponse)
def root():
    return _HTML_CONTENT


@app.get("/api/platforms")
def list_platforms():
    return PLATFORM_META


@app.get("/api/platforms/{platform}/profiles")
def list_profiles(platform: str):
    return browser_manager.list_profiles(platform)


@app.post("/api/platforms/{platform}/profiles/{profile_name}")
async def create_profile(platform: str, profile_name: str):
    """Create a new browser profile and open the platform so user can log in."""
    if platform not in PLATFORMS:
        raise HTTPException(400, f"Unknown platform: {platform}")
    try:
        page = await browser_manager.get_page(platform, profile_name)
        PlatformClass = PLATFORMS[platform]
        ai = PlatformClass(page)
        await page.goto(ai.url, wait_until="domcontentloaded", timeout=20000)
        return {"ok": True, "profile": profile_name, "url": ai.url,
                "message": f"Browser opened — log in to {platform} and close the tab when done."}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/query")
async def run_query(req: QueryRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "Prompt cannot be empty")

    selected = [p for p in req.platforms if p in PLATFORMS]
    if not selected:
        raise HTTPException(400, "No valid platforms selected")

    session_id = str(uuid.uuid4())[:8]
    active_sessions[session_id] = {
        "prompt":    req.prompt,
        "platforms": selected,
        "responses": {},
        "status":    "running",
    }

    asyncio.create_task(run_session(session_id, req.prompt, selected, req.profiles))
    return {"session_id": session_id}


async def run_platform(session_id: str, platform_key: str, prompt: str, profile: str):
    await ws_manager.send_status(session_id, platform_key, "waiting", "Opening browser…")
    import importlib.resources as _ir, json as _j
    try:
        _sel = _j.loads(_ir.files("chorus").joinpath("selectors.json").read_text())
    except Exception:
        _sel = {}
    platform_timeout = _sel.get(platform_key, {}).get("timeout_seconds", 60)
    page_text = ""
    try:
        page = await browser_manager.get_page(platform_key, profile)
        PlatformClass = PLATFORMS[platform_key]
        ai = PlatformClass(page)

        await ws_manager.send_status(session_id, platform_key, "typing", "Submitting prompt…")
        await asyncio.wait_for(ai.submit_prompt(prompt), timeout=platform_timeout)

        await ws_manager.send_status(session_id, platform_key, "typing", "Waiting for response…")
        response = await asyncio.wait_for(
            ai.wait_for_response(timeout=platform_timeout),
            timeout=platform_timeout + 5,
        )

        active_sessions[session_id]["responses"][platform_key] = response
        await ws_manager.send_status(session_id, platform_key, "done", "Done", response)

    except Exception as e:
        try:
            page = await browser_manager.get_page(platform_key, profile)
            page_text = await page.content()
        except Exception:
            pass
        error_code, message = _classify_error(platform_key, e, page_text)

        # Best-effort auth expiry check — page may be in broken state
        try:
            p = await browser_manager.get_page(platform_key, profile)
            ai = PLATFORMS[platform_key](p)
            if not await asyncio.wait_for(ai.is_authenticated(), timeout=5):
                error_code, message = "auth_expired", (
                    f"Your {platform_key.capitalize()} session has expired. "
                    "Click Re-login to reconnect."
                )
        except Exception:
            pass  # auth check is best-effort

        active_sessions[session_id]["responses"][platform_key] = {
            "error": True, "error_code": error_code, "message": message,
        }
        await ws_manager.send_status(
            session_id, platform_key, "error",
            f"[{error_code}] {message}",
        )


async def run_session(session_id: str, prompt: str, platforms: list[str], profiles: dict):
    tasks = [
        run_platform(session_id, p, prompt, profiles.get(p, "default"))
        for p in platforms
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    active_sessions[session_id]["status"] = "complete"
    responses = active_sessions[session_id]["responses"]

    # Persist to history
    entry = {
        "id":         session_id,
        "prompt":     prompt,
        "platforms":  platforms,
        "responses":  responses,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    prompt_history.append(entry)
    save_history()

    await ws_manager.broadcast({
        "type":       "session_complete",
        "session_id": session_id,
        "responses":  responses,
        "prompt":     prompt,
    })


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    if session_id not in active_sessions:
        raise HTTPException(404)
    return active_sessions[session_id]


_retry_locks: dict = {}  # key = "{session_id}:{platform}"


@app.post("/api/sessions/{session_id}/retry/{platform}")
async def retry_platform(session_id: str, platform: str):
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    lock_key = f"{session_id}:{platform}"
    lock = _retry_locks.setdefault(lock_key, asyncio.Lock())

    if lock.locked():
        raise HTTPException(status_code=409, detail="Retry already in progress for this platform")

    session = active_sessions[session_id]
    retrying: set = session.setdefault("_retrying", set())

    if platform in retrying:
        raise HTTPException(status_code=409, detail="Retry already in progress for this platform")

    retry_count = session.setdefault("_retry_counts", {})
    if retry_count.get(platform, 0) >= 3:
        raise HTTPException(status_code=422, detail=_json.dumps({"error": "Max retries reached", "code": "max_retries"}))

    retrying.add(platform)
    retry_count[platform] = retry_count.get(platform, 0) + 1

    profile = session.get("profiles", {}).get(platform, "default")
    asyncio.create_task(_retry_and_cleanup(session_id, platform, session["prompt"], profile))
    return {"ok": True}


async def _retry_and_cleanup(session_id: str, platform: str, prompt: str, profile: str):
    try:
        await run_platform(session_id, platform, prompt, profile)
    finally:
        active_sessions.get(session_id, {}).get("_retrying", set()).discard(platform)


@app.post("/api/sessions/{session_id}/followup")
async def followup_session(session_id: str, req: FollowUpRequest):
    """Send a follow-up prompt to the same browser pages (conversational context)."""
    if session_id not in active_sessions:
        raise HTTPException(404, "Session not found — start a new query first")
    if not req.prompt.strip():
        raise HTTPException(400, "Follow-up prompt cannot be empty")

    session = active_sessions[session_id]
    if session["status"] == "running":
        raise HTTPException(409, "Previous query still running")

    platforms = session["platforms"]
    profiles  = session.get("profiles", {})

    # Reuse existing session — just send new prompt to same pages
    new_id = str(uuid.uuid4())[:8]
    active_sessions[new_id] = {
        "prompt":    req.prompt,
        "platforms": platforms,
        "responses": {},
        "status":    "running",
        "parent_id": session_id,
        "profiles":  profiles,
    }
    asyncio.create_task(run_followup(new_id, session_id, req.prompt, platforms))
    return {"session_id": new_id, "parent_id": session_id}


async def run_followup(session_id: str, parent_id: str, prompt: str, platforms: list[str]):
    """Send follow-up on existing browser pages without navigating away."""
    tasks = [
        run_followup_platform(session_id, p, prompt)
        for p in platforms
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    active_sessions[session_id]["status"] = "complete"
    responses = active_sessions[session_id]["responses"]

    entry = {
        "id":         session_id,
        "prompt":     prompt,
        "platforms":  platforms,
        "responses":  responses,
        "parent_id":  parent_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    prompt_history.append(entry)
    save_history()

    await ws_manager.broadcast({
        "type":       "session_complete",
        "session_id": session_id,
        "responses":  responses,
        "prompt":     prompt,
        "is_followup": True,
        "parent_id":  parent_id,
    })


async def run_followup_platform(session_id: str, platform_key: str, prompt: str):
    """Submit follow-up to an existing page without reloading."""
    await ws_manager.send_status(session_id, platform_key, "typing", "Submitting follow-up…")
    try:
        # Get the existing page (already on the chat)
        page = await browser_manager.get_page(platform_key, "default")
        PlatformClass = PLATFORMS[platform_key]
        ai = PlatformClass(page)

        # Type into the existing input (no navigate — keeps conversation context)
        input_sel = ai._input_sel()
        el = await page.wait_for_selector(input_sel, timeout=10000)
        await el.click()
        tag = await el.evaluate("el => el.tagName.toLowerCase()")
        if tag == "textarea":
            await el.fill(prompt)
        else:
            await page.keyboard.type(prompt, delay=10)

        send_sel = ai._send_sel()
        if send_sel:
            try:
                btn = await page.wait_for_selector(send_sel, timeout=3000)
                await btn.click()
            except Exception:
                await page.keyboard.press("Enter")
        else:
            await page.keyboard.press("Enter")

        await ws_manager.send_status(session_id, platform_key, "typing", "Waiting for reply…")
        response = await ai.wait_for_response(timeout=120)

        # Return only the new portion (last response block)
        active_sessions[session_id]["responses"][platform_key] = response
        await ws_manager.send_status(session_id, platform_key, "done", "Done", response)

    except Exception as e:
        error_code, message = _classify_error(platform_key, e)
        active_sessions[session_id]["responses"][platform_key] = {
            "error": True, "error_code": error_code, "message": message,
        }
        await ws_manager.send_status(session_id, platform_key, "error", message)


@app.get("/api/history")
def get_history(limit: int = 30):
    return list(reversed(prompt_history[-limit:]))


@app.delete("/api/history/{session_id}")
def delete_history_item(session_id: str):
    global prompt_history
    prompt_history = [h for h in prompt_history if h["id"] != session_id]
    save_history()
    return {"ok": True}


@app.get("/api/export/{session_id}", response_class=PlainTextResponse)
def export_session(session_id: str):
    """Export a session as a Markdown document."""
    entry = next((h for h in prompt_history if h["id"] == session_id), None)
    if not entry:
        # Try active sessions
        s = active_sessions.get(session_id)
        if not s:
            raise HTTPException(404)
        entry = {**s, "id": session_id,
                 "created_at": datetime.now(timezone.utc).isoformat()}

    lines = [
        f"# Chorus Session — {entry['id']}",
        f"**Date:** {entry.get('created_at','')[:19].replace('T',' ')} UTC",
        f"**Platforms:** {', '.join(entry.get('platforms',[]))}",
        "",
        "## Prompt",
        "",
        entry.get("prompt", ""),
        "",
        "---",
        "",
    ]
    for platform, resp in (entry.get("responses") or {}).items():
        meta = PLATFORM_META.get(platform, {"name": platform, "icon": "🤖"})
        if isinstance(resp, dict):
            resp_text = f"_Error: {resp.get('message', 'unknown error')}_"
        else:
            resp_text = resp or "_No response_"
        lines += [
            f"## {meta['icon']} {meta['name']}",
            "",
            resp_text,
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


@app.get("/api/sessions/{session_id}/consensus")
def get_consensus(session_id: str):
    """
    Analyse all responses for a session and return:
    - agreed_themes   : points mentioned by >= 50 % of platforms
    - unique_points   : points found only in one platform's response
    - platform_scores : pairwise Jaccard similarity between platforms
    - top_keywords    : top-10 keywords per platform (TF-style, stop-words stripped)
    - summary_stats   : word count, sentence count per platform
    """
    entry = next((h for h in prompt_history if h["id"] == session_id), None)
    if not entry:
        s = active_sessions.get(session_id)
        if not s or s.get("status") != "complete":
            raise HTTPException(404, "Session not found or still running")
        entry = {**s, "id": session_id}

    responses: dict[str, str] = {
        k: v for k, v in (entry.get("responses") or {}).items()
        if isinstance(v, str) and v and not v.startswith("[Error")
    }
    if not responses:
        raise HTTPException(422, "No valid responses to analyse")

    return _build_consensus(responses)


_STOP_WORDS = {
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "is","are","was","were","be","been","being","have","has","had","do","does",
    "did","will","would","could","should","may","might","can","this","that",
    "these","those","i","you","he","she","it","we","they","my","your","its",
    "our","their","also","as","from","by","not","no","so","if","then","than",
    "when","where","which","who","what","how","all","any","each","more","most",
    "other","some","such","into","up","out","about","just","like","use","using",
    "used","get","gets","got","make","makes","made","one","two","first","second",
}


def _tokenize_sentences(text: str) -> list[str]:
    import re
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sents if len(s.strip()) > 20]


def _keywords(text: str, top_n: int = 10) -> list[str]:
    import re
    words = re.findall(r"[a-z]{3,}", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOP_WORDS:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:top_n]]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _sentence_words(s: str) -> set[str]:
    import re
    return {w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in _STOP_WORDS}


def _build_consensus(responses: dict[str, str]) -> dict:
    platforms = list(responses.keys())
    n = len(platforms)

    # ── Sentence sets per platform ────────────────────────────────────
    sent_sets = {p: _tokenize_sentences(responses[p]) for p in platforms}
    word_sets = {p: _sentence_words(responses[p]) for p in platforms}

    # ── Pairwise platform similarity ──────────────────────────────────
    platform_scores: dict[str, dict[str, float]] = {}
    for i, pa in enumerate(platforms):
        platform_scores[pa] = {}
        for pb in platforms[i+1:]:
            score = round(_jaccard(word_sets[pa], word_sets[pb]), 3)
            platform_scores[pa][pb] = score

    # ── Agreed themes: sentences from one platform that have a
    #    Jaccard match >= 0.25 in >= half the other platforms ──────────
    AGREE_THRESH  = 0.25
    AGREE_MIN_PCT = 0.5        # fraction of *other* platforms needed

    agreed_raw:  list[dict] = []
    unique_raw:  list[dict] = []
    seen_agreed: set[str]   = set()

    for p in platforms:
        for sent in sent_sets[p]:
            if sent in seen_agreed:
                continue
            sw = _sentence_words(sent)
            matches = []
            for other in platforms:
                if other == p:
                    continue
                best = max(
                    (_jaccard(sw, _sentence_words(os_)) for os_ in sent_sets[other]),
                    default=0.0,
                )
                if best >= AGREE_THRESH:
                    matches.append(other)

            coverage = len(matches) / max(n - 1, 1)
            if coverage >= AGREE_MIN_PCT:
                agreed_raw.append({
                    "sentence":  sent,
                    "platforms": [p] + matches,
                    "coverage":  round(coverage, 2),
                })
                seen_agreed.add(sent)
            elif not matches:
                unique_raw.append({"sentence": sent, "platform": p})

    # Deduplicate agreed themes (keep highest coverage)
    agreed_raw.sort(key=lambda x: -x["coverage"])
    agreed_themes = agreed_raw[:15]

    # Keep unique points (max 5 per platform)
    by_plat: dict[str, list] = {p: [] for p in platforms}
    for u in unique_raw:
        lst = by_plat[u["platform"]]
        if len(lst) < 5:
            lst.append(u["sentence"])
    unique_points = {p: sents for p, sents in by_plat.items() if sents}

    # ── Keywords & stats ──────────────────────────────────────────────
    import re
    top_keywords   = {p: _keywords(responses[p]) for p in platforms}
    summary_stats  = {
        p: {
            "words":     len(re.findall(r"\S+", responses[p])),
            "sentences": len(sent_sets[p]),
            "chars":     len(responses[p]),
        }
        for p in platforms
    }

    # ── Consensus keywords (in >= half of platforms' top lists) ───────
    kw_counts: dict[str, int] = {}
    for kws in top_keywords.values():
        for kw in kws:
            kw_counts[kw] = kw_counts.get(kw, 0) + 1
    consensus_keywords = [
        kw for kw, cnt in sorted(kw_counts.items(), key=lambda x: -x[1])
        if cnt >= max(n // 2, 1)
    ][:15]

    return {
        "session_id":        None,   # filled by caller if needed
        "platform_count":    n,
        "agreed_themes":     agreed_themes,
        "unique_points":     unique_points,
        "platform_scores":   platform_scores,
        "top_keywords":      top_keywords,
        "consensus_keywords": consensus_keywords,
        "summary_stats":     summary_stats,
    }


# ── Onboarding ────────────────────────────────────────────────────────────────

@app.post("/api/onboarding/complete")
def onboarding_complete():
    """Called when the wizard is dismissed."""
    return {"ok": True}


@app.get("/api/onboarding/state")
def get_onboarding_state():
    """Return full onboarding state for the wizard UI."""
    return _onboarding.load_state(_ONBOARDING_FILE)


@app.post("/api/onboarding/{platform}/open")
async def onboarding_open(platform: str):
    """Open a page in the shared Chrome profile for the user to log in."""
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
    try:
        page = await browser_manager.get_page(f"onboard_{platform}")
        platform_instance = PLATFORMS[platform](page)
        await page.goto(platform_instance.url, wait_until="domcontentloaded", timeout=20000)
        _onboarding_pages[platform] = page
        return {"ok": True, "message": f"Browser opened for {platform}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/onboarding/{platform}/status")
async def onboarding_status(platform: str):
    """Poll authentication state. Marks platform complete when logged in."""
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    page = _onboarding_pages.get(platform)
    if page is None or page.is_closed():
        return {"authenticated": False, "profile_exists": True}

    try:
        platform_instance = PLATFORMS[platform](page)
        authenticated = await platform_instance.is_authenticated()
        if authenticated:
            _onboarding_pages.pop(platform, None)
            _onboarding.mark_completed(platform, _ONBOARDING_FILE)
        return {"authenticated": authenticated, "profile_exists": True}
    except Exception as e:
        return {"authenticated": False, "profile_exists": True, "error": str(e)}


@app.post("/api/onboarding/{platform}/skip")
def onboarding_skip(platform: str):
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
    _onboarding.mark_skipped(platform, _ONBOARDING_FILE)
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


def _check_playwright():
    """Exit with clear message if Playwright Chromium binary is missing."""
    try:
        with sync_playwright() as p:
            binary = p.chromium.executable_path
            if not Path(binary).exists():
                raise FileNotFoundError(f"Chromium binary not found at {binary}")
    except Exception:
        print("Playwright Chromium not found. Run: playwright install chromium")
        print("Then restart chorus.")
        sys.exit(1)


def main():
    """Entry point for `chorus` CLI command."""
    _CHORUS_DIR.mkdir(parents=True, exist_ok=True)
    _check_playwright()

    port = 4747

    def _open_browser():
        import time
        time.sleep(1.5)
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("chorus.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
