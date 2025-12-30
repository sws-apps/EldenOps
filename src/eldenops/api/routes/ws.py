"""WebSocket routes for real-time updates."""

from __future__ import annotations

import asyncio
from datetime import datetime

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from eldenops.api.websocket import get_manager
from eldenops.config.settings import settings

router = APIRouter()
logger = structlog.get_logger()


@router.post("/test-broadcast/{tenant_id}")
async def test_broadcast(tenant_id: str) -> dict:
    """Test endpoint to verify WebSocket broadcasting works.

    Sends a test attendance update to all connected clients for the tenant.
    """
    manager = get_manager()
    connection_count = manager.get_connection_count(tenant_id)

    if connection_count == 0:
        return {
            "status": "no_connections",
            "message": f"No WebSocket connections for tenant {tenant_id}",
        }

    # Broadcast a test event
    await manager.broadcast_attendance_update(
        tenant_id,
        {
            "user_id": "test-user",
            "discord_id": 0,
            "discord_username": "Test User",
            "status": "active",
            "event_type": "checkin",
            "reason": None,
            "expected_return_at": None,
            "last_checkin_at": datetime.utcnow().isoformat(),
            "last_checkout_at": None,
            "is_test": True,
        }
    )

    return {
        "status": "broadcast_sent",
        "connections": connection_count,
        "message": f"Test broadcast sent to {connection_count} connection(s)",
    }


@router.websocket("/ws/{tenant_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    tenant_id: str,
    token: str = Query(...),
) -> None:
    """
    WebSocket endpoint for real-time updates.

    Clients connect with their tenant_id and JWT token for authentication.
    Events broadcast to this connection:
    - attendance_update: When a user's attendance status changes
    - discord_event: When Discord messages/voice events occur
    - github_event: When GitHub webhooks are received
    """
    manager = get_manager()

    # Verify the JWT token
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("user_id")
        # The token contains primary_tenant_id which is the user's current tenant
        token_tenant_id = payload.get("primary_tenant_id")

        # Verify the user has access to this tenant
        if token_tenant_id != tenant_id:
            logger.warning("WebSocket tenant mismatch", token_tenant=token_tenant_id, requested_tenant=tenant_id)
            await websocket.close(code=4003, reason="Tenant mismatch")
            return

        logger.info("WebSocket authenticated", user_id=user_id, tenant_id=tenant_id)

    except JWTError as e:
        logger.warning("WebSocket auth failed", error=str(e))
        await websocket.close(code=4001, reason="Invalid token")
        return

    await manager.connect(websocket, tenant_id)

    try:
        # Keep the connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages (ping/pong or commands)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_text('{"type":"ping"}')
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", tenant_id=tenant_id)
    except Exception as e:
        logger.error("WebSocket error", error=str(e), tenant_id=tenant_id)
    finally:
        await manager.disconnect(websocket, tenant_id)
