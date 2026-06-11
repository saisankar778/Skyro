"""
ws_manager.py - WebSocketManager + background broadcaster task

Manages all connected WebSocket clients and fans out telemetry every 2 s.

Design:
  R8 - A SINGLE broadcaster task wakes every 2 s, reads DroneState caches,
       and fans out via asyncio.gather.  Slow/dead clients are removed without
       blocking the broadcast loop.  The broadcaster never queries MAVSDK.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Set, TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    from drone_registry import DroneRegistry

logger = logging.getLogger("ws_manager")

BROADCAST_INTERVAL_S: float = 2.0


class WebSocketManager:
    """
    Tracks all active WebSocket connections and runs a single background
    broadcaster task.

    _clients: Set[WebSocket]
        All currently connected WS clients.  Modified from the single asyncio
        event loop - no additional locking required.

    broadcaster_task: asyncio.Task | None
        The single background task that broadcasts every 2 s.
    """

    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self.broadcaster_task: asyncio.Task | None = None

    # --------------------------------------------------------------------------
    # Client management
    # --------------------------------------------------------------------------

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WS client."""
        await websocket.accept()
        self._clients.add(websocket)
        logger.info(
            "WebSocket client connected. Total clients: %d", len(self._clients)
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WS client from the pool."""
        self._clients.discard(websocket)
        logger.info(
            "WebSocket client disconnected. Total clients: %d", len(self._clients)
        )

    # --------------------------------------------------------------------------
    # Broadcast
    # --------------------------------------------------------------------------

    async def broadcast(self, payload: dict) -> None:
        """
        Fan out payload to all connected clients concurrently.
        Dead clients are silently removed.
        """
        if not self._clients:
            return

        message = json.dumps(payload)

        async def _send(ws: WebSocket) -> WebSocket | None:
            try:
                await ws.send_text(message)
                return None  # success - no removal needed
            except Exception:
                return ws   # signal that this client should be removed

        results = await asyncio.gather(
            *(_send(ws) for ws in list(self._clients)),
            return_exceptions=False,
        )

        for result in results:
            if result is not None:
                self._clients.discard(result)
                logger.debug("Removed dead WebSocket client.")

    # --------------------------------------------------------------------------
    # Background broadcaster task (R8)
    # --------------------------------------------------------------------------

    async def start_broadcaster(self, registry: "DroneRegistry") -> None:
        """
        Single background task: wake every 2 s, read DroneState caches from the
        registry (no MAVSDK calls), build the frozen broadcast schema, and fan
        out to all connected WS clients.
        """
        logger.info("WebSocket broadcaster started (interval=%ss).", BROADCAST_INTERVAL_S)
        try:
            while True:
                await asyncio.sleep(BROADCAST_INTERVAL_S)

                drone_states = registry.get_all_states_dict()

                payload = {
                    "type": "status_update",
                    "drones": drone_states,
                }

                await self.broadcast(payload)

        except asyncio.CancelledError:
            logger.info("WebSocket broadcaster cancelled.")
            raise
        except Exception as exc:
            logger.error("WebSocket broadcaster crashed: %s", exc, exc_info=True)
            raise
