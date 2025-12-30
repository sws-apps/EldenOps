"""WebSocket manager for real-time updates."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    """Manages WebSocket connections per tenant."""

    def __init__(self) -> None:
        # tenant_id -> list of WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, tenant_id: str) -> None:
        """Accept a new WebSocket connection for a tenant."""
        await websocket.accept()
        async with self._lock:
            if tenant_id not in self.active_connections:
                self.active_connections[tenant_id] = []
            self.active_connections[tenant_id].append(websocket)
        logger.info("WebSocket connected", tenant_id=tenant_id, total_connections=len(self.active_connections.get(tenant_id, [])))

    async def disconnect(self, websocket: WebSocket, tenant_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if tenant_id in self.active_connections:
                try:
                    self.active_connections[tenant_id].remove(websocket)
                except ValueError:
                    pass
                if not self.active_connections[tenant_id]:
                    del self.active_connections[tenant_id]
        logger.info("WebSocket disconnected", tenant_id=tenant_id)

    async def broadcast_to_tenant(self, tenant_id: str, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast a message to all connections for a tenant."""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        connections = self.active_connections.get(tenant_id, [])
        if not connections:
            return

        # Serialize the message once
        message_json = json.dumps(message, default=str)

        # Send to all connections, removing any that fail
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning("Failed to send WebSocket message", error=str(e))
                disconnected.append(websocket)

        # Clean up disconnected sockets
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    try:
                        self.active_connections[tenant_id].remove(ws)
                    except (ValueError, KeyError):
                        pass

    async def broadcast_attendance_update(self, tenant_id: str | UUID, user_data: dict[str, Any]) -> None:
        """Broadcast an attendance status update."""
        await self.broadcast_to_tenant(
            str(tenant_id),
            "attendance_update",
            user_data
        )

    async def broadcast_discord_event(self, tenant_id: str | UUID, event_data: dict[str, Any]) -> None:
        """Broadcast a Discord event (message, voice, etc.)."""
        await self.broadcast_to_tenant(
            str(tenant_id),
            "discord_event",
            event_data
        )

    async def broadcast_github_event(self, tenant_id: str | UUID, event_data: dict[str, Any]) -> None:
        """Broadcast a GitHub event."""
        await self.broadcast_to_tenant(
            str(tenant_id),
            "github_event",
            event_data
        )

    def get_connection_count(self, tenant_id: str) -> int:
        """Get the number of active connections for a tenant."""
        return len(self.active_connections.get(tenant_id, []))


# Global connection manager instance
manager = ConnectionManager()


def get_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager
