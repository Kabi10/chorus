import asyncio
import uuid
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from chorus.browser import manager as browser_manager
from chorus.websocket_manager import ws_manager
from chorus.platforms.gemini import Gemini
from chorus.platforms.chatgpt import ChatGPT
from chorus.platforms.claude import Claude
from chorus.platforms.perplexity import Perplexity

HTML_FILE = Path(__file__).parent / "frontend" / "index.html"

PLATFORMS = {
    "gemini":     Gemini,
    "chatgpt":    ChatGPT,
    "claude":     Claude,
    "perplexity": Perplexity,
}

PLATFORM_META = {
    "gemini":     {"name": "Gemini",     "color": "#4285F4", "icon": "🌀"},
    "chatgpt":    {"name": "ChatGPT",    "color": "#10a37f", "icon": "🟢"},
    "claude":     {"name": "Claude",     "color": "#d97706", "icon": "🟣"},
    "perplexity": {"name": "Perplexity", "color": "#20b8cd", "icon": "🔭"},
}

app = FastAPI(title="Chorus")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

active_sessions: dict[str, dict] = {}


class QueryRequest(BaseModel):
    prompt:    str
    platforms: list[str] = list(PLATFORMS.keys())
    profiles:  dict[str, str] = {}


@app.on_event("startup")
async def startup():
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
    await ws_manager.broadcast({
        "type":       "session_complete",
        "session_id": session_id,
        "responses":  active_sessions[session_id]["responses"],
        "prompt":     prompt,
    })


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    if session_id not in active_sessions:
        raise HTTPException(404)
    return active_sessions[session_id]


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
