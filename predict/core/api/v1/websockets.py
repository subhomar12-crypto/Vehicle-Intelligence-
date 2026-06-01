"""
WebSocket endpoints for real-time data streaming.

Provides WebSocket connections for:
- User-specific notifications
- Vehicle live data streaming
- Real-time alerts
"""

import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from predict.core.services.websocket_service import ws_manager
from predict.core.middleware.api_key import validate_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_admin_endpoint(websocket: WebSocket):
    """
    Generic WebSocket endpoint for desktop/admin connections.
    No user_id required — used for broadcast monitoring.
    """
    channel = "admin_desktop"
    await ws_manager.connect(websocket, channel)
    try:
        await websocket.send_json({"type": "connected", "channel": channel})
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, channel)
        logger.info("Desktop admin WebSocket disconnected")
    except Exception as e:
        logger.error(f"Desktop admin WebSocket error: {e}")
        await ws_manager.disconnect(websocket, channel)


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """
    General WebSocket endpoint for user notifications.
    
    Args:
        websocket: WebSocket connection
        user_id: User ID for the connection
    """
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            # Receive and echo back (or process commands)
            data = await websocket.receive_json()
            
            # Echo back with acknowledgment
            await ws_manager.send_to_user(user_id, {
                "type": "echo",
                "data": data,
                "timestamp": __import__('time').time(),
            })
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, user_id)
        logger.info(f"User {user_id} disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        await ws_manager.disconnect(websocket, user_id)


@router.websocket("/ws/vehicle/{profile_id}/live")
async def vehicle_live_data_websocket(
    websocket: WebSocket,
    profile_id: int,
):
    """
    WebSocket for live OBD data streaming from a vehicle.
    
    Args:
        websocket: WebSocket connection
        profile_id: Vehicle profile ID
    """
    # Create a unique channel for this vehicle
    channel = f"vehicle_{profile_id}"
    
    await ws_manager.connect(websocket, channel)
    
    # Notify connected
    await ws_manager.broadcast_to_channel(channel, {
        "type": "status",
        "message": "Live data stream connected",
        "profile_id": profile_id,
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Validate and process incoming OBD data
            if data.get("type") == "obd_data":
                # Broadcast to all connected clients for this vehicle
                await ws_manager.broadcast_to_channel(channel, {
                    "type": "live_data",
                    "profile_id": profile_id,
                    "data": data.get("readings", {}),
                    "timestamp": __import__('time').time(),
                })
            
            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, channel)
        logger.info(f"Vehicle {profile_id} live stream disconnected")
    except Exception as e:
        logger.error(f"Vehicle live stream error: {e}")
        await ws_manager.disconnect(websocket, channel)


@router.websocket("/ws/alerts/{user_id}")
async def alerts_websocket(websocket: WebSocket, user_id: int):
    """
    WebSocket for real-time alert notifications.
    
    Args:
        websocket: WebSocket connection
        user_id: User ID to receive alerts for
    """
    alert_channel = f"alerts_{user_id}"
    
    await ws_manager.connect(websocket, alert_channel)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "channel": "alerts",
            "user_id": user_id,
        })
        
        while True:
            # Keep connection alive, alerts are pushed from server
            data = await websocket.receive_text()
            
            # Handle ping/heartbeat
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, alert_channel)
        logger.info(f"Alerts WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"Alerts WebSocket error: {e}")
        await ws_manager.disconnect(websocket, alert_channel)


@router.websocket("/ws/guardian/{guardian_id}")
async def guardian_websocket(websocket: WebSocket, guardian_id: str):
    """
    WebSocket for Guardian mode real-time updates.
    
    Args:
        websocket: WebSocket connection
        guardian_id: Guardian ID
    """
    channel = f"guardian_{guardian_id}"
    
    await ws_manager.connect(websocket, channel)
    
    try:
        await websocket.send_json({
            "type": "connected",
            "channel": "guardian",
            "guardian_id": guardian_id,
        })
        
        while True:
            data = await websocket.receive_json()
            
            # Handle guardian commands
            if data.get("type") == "location_request":
                # Forward to vehicle
                vehicle_id = data.get("vehicle_id")
                await ws_manager.broadcast_to_channel(
                    f"vehicle_{vehicle_id}",
                    {
                        "type": "location_request",
                        "guardian_id": guardian_id,
                    }
                )
    
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, channel)
        logger.info(f"Guardian {guardian_id} disconnected")
    except Exception as e:
        logger.error(f"Guardian WebSocket error: {e}")
        await ws_manager.disconnect(websocket, channel)


# REST endpoints for WebSocket management

@router.post("/ws/broadcast")
async def broadcast_message(
    message: dict,
    current_user: dict = Depends(validate_api_key),
):
    """
    Broadcast a message to all connected users (admin only).
    
    Args:
        message: Message to broadcast
    """
    await ws_manager.broadcast({
        "type": "broadcast",
        "message": message.get("text", ""),
        "timestamp": __import__('time').time(),
    })
    return {"status": "broadcast sent", "connections": len(ws_manager.active_connections)}


@router.get("/ws/stats")
async def get_websocket_stats(
    current_user: dict = Depends(validate_api_key),
) -> dict:
    """Get WebSocket connection statistics."""
    return {
        "active_connections": len(ws_manager.active_connections),
        "channels": list(ws_manager.channels.keys()),
        "connection_count_by_channel": {
            channel: len(conns) 
            for channel, conns in ws_manager.channels.items()
        },
    }
