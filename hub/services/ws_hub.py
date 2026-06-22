"""Shared WebSocket connection hub for broadcasting hub-wide events."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketHub:
    """Tracks active WebSocket clients and broadcasts JSON events."""

    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients)

        if not clients:
            return

        stale: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(message)
            except Exception as exc:
                logger.debug("WebSocket broadcast failed: %s", exc)
                stale.append(ws)

        if stale:
            async with self._lock:
                for ws in stale:
                    self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)