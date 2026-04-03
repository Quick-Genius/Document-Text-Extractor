from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.core.websocket_manager import websocket_manager
from app.core.auth import get_current_user_id
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        user_id = await get_current_user_id_from_token(token)
        await websocket_manager.connect(websocket, user_id)
        while True:
            data = await websocket.receive_json()
            if data["type"] == "subscribe":
                await websocket_manager.subscribe(user_id, data["jobId"])
            elif data["type"] == "unsubscribe":
                await websocket_manager.unsubscribe(user_id, data["jobId"])
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, user_id)
        logger.info(f"User {user_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

async def get_current_user_id_from_token(token: str) -> str:
    # This is a simplified way to get the user ID from the token.
    # In a real application, you would use a proper JWT library to decode and verify the token.
    # For this implementation, we will assume the token is the user ID.
    return token
