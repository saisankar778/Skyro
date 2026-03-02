from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_active_connections: List[WebSocket] = []

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _active_connections.append(ws)
    try:
        while True:
            # keep connection alive; clients can send pings if they wish
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in _active_connections:
            _active_connections.remove(ws)

async def broadcast(message: dict):
    dead = []
    for conn in _active_connections:
        try:
            await conn.send_json(message)
        except Exception:
            dead.append(conn)
    for d in dead:
        if d in _active_connections:
            _active_connections.remove(d)
