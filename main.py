import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from chorus.browser import manager as browser_manager
from chorus.websocket_manager import ws_manager
from chorus.platforms.gemini import Gemini
from chorus.platforms.chatgpt import ChatGPT
from chorus.platforms.claude import Claude
from chorus.platforms.perplexity import Perplexity
from chorus.platforms.grok import Grok
from chorus.platforms.copilot import Copilot
from chorus.platforms.deepseek import DeepSeek
from chorus.platforms.mistral import Mistral

HTML_FILE    = Path(__file__).parent / "frontend" / "index.html"
HISTORY_FILE = Path(__file__).parent / "chorus_history.json"
MAX_HISTORY  = 100

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


@app.on_event("startup")
async def startup():
    load_history()
    await browser_manager.start()
    print("Chorus running at http://localhost:4747")


@app.on_event("shutdown")
async def shutdown():
    await browser_manager.stop()


@app.get("/", response_class=HTMLResponse)
def root():
    return HTML_FILE.read_text(encoding="utf-8")


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
    try:
        page = await browser_manager.get_page(platform_key, profile)
        PlatformClass = PLATFORMS[platform_key]
        ai = PlatformClass(page)

        await ws_manager.send_status(session_id, platform_key, "typing", "Submitting prompt…")
        await ai.submit_prompt(prompt)

        await ws_manager.send_status(session_id, platform_key, "typing", "Waiting for response…")
        response = await ai.wait_for_response(timeout=120)

        active_sessions[session_id]["responses"][platform_key] = response
        await ws_manager.send_status(session_id, platform_key, "done", "Done", response)

    except Exception as e:
        err = str(e)
        active_sessions[session_id]["responses"][platform_key] = f"[Error: {err}]"
        await ws_manager.send_status(session_id, platform_key, "error", err)


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
        lines += [
            f"## {meta['icon']} {meta['name']}",
            "",
            resp or "_No response_",
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4747, reload=False)
