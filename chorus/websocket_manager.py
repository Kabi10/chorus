"""WebSocket broadcast manager — streams per-AI progress to the frontend."""
from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_status(self, session_id: str, platform: str, status: str,
                          message: str = "", response: str = ""):
        await self.broadcast({
            "type":       "platform_update",
            "session_id": session_id,
            "platform":   platform,
            "status":     status,   # waiting | typing | done | error
            "message":    message,
            "response":   response,
        })


ws_manager = WSManager()
