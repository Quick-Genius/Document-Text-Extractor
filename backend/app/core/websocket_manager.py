from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
from app.utils.redis_client import redis_client
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manage WebSocket connections and broadcast progress updates"""
    
    def __init__(self):
        # user_id -> set of WebSocket connections
        self.connections: Dict[str, Set[WebSocket]] = {}
        
        # job_id -> set of user_ids subscribed
        self.job_subscriptions: Dict[str, Set[str]] = {}
        
        # Background task for Redis Pub/Sub
        self.pubsub_task: asyncio.Task = None
        self.running = False
    
    async def start(self):
        """Start the WebSocket manager and Redis listener"""
        self.running = True
        self.pubsub_task = asyncio.create_task(self.listen_to_redis())
        logger.info("WebSocket manager started")
    async def stop(self):
        """Stop the WebSocket manager"""
        self.running = False
        if self.pubsub_task:
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass
        logger.info("WebSocket manager stopped")
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Register a new WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.connections:
            self.connections[user_id] = set()
        
        self.connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected, total connections: {len(self.connections[user_id])}")
    
    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Unregister a WebSocket connection"""
        if user_id in self.connections:
            self.connections[user_id].discard(websocket)
            
            if not self.connections[user_id]:
                del self.connections[user_id]
                
                # Clean up subscriptions
                for job_id, subscribers in list(self.job_subscriptions.items()):
                    subscribers.discard(user_id)
                    if not subscribers:
                        del self.job_subscriptions[job_id]
        
        logger.info(f"User {user_id} disconnected")
    
    async def subscribe(self, user_id: str, job_id: str):
        """Subscribe a user to job updates"""
        if job_id not in self.job_subscriptions:
            self.job_subscriptions[job_id] = set()
        
        self.job_subscriptions[job_id].add(user_id)
        logger.debug(f"User {user_id} subscribed to job {job_id}")
        
        # Send current job status immediately
        await self.send_current_status(user_id, job_id)
    
    async def unsubscribe(self, user_id: str, job_id: str):
        """Unsubscribe a user from job updates"""
        if job_id in self.job_subscriptions:
            self.job_subscriptions[job_id].discard(user_id)
            
            if not self.job_subscriptions[job_id]:
                del self.job_subscriptions[job_id]
        
        logger.debug(f"User {user_id} unsubscribed from job {job_id}")
    
    async def send_current_status(self, user_id: str, job_id: str):
        """Send current job status from Redis cache"""
        try:
            progress_data = await redis_client.hgetall(f"job:progress:{job_id}")
            
            if progress_data:
                message = {
                    "type": "progress",
                    "jobId": job_id,
                    "data": {
                        "status": progress_data.get("status", "unknown"),
                        "message": progress_data.get("message", ""),
                        "progress": int(progress_data.get("progress", 0)),
                        "timestamp": float(progress_data.get("updated_at", 0)),
                    }
                }
                
                await self.send_to_user(user_id, message)
        except Exception as e:
            logger.error(f"Error sending current status: {e}")
    
    async def listen_to_redis(self):
        """Listen to Redis Pub/Sub for progress updates"""
        pubsub = await redis_client.subscribe("progress:*")

        try:
            async for message in pubsub.listen():
                if not self.running:
                    break
                # psubscribe yields type "pmessage"; subscribe yields "message"
                if message and message["type"] in ("message", "pmessage"):
                    await self.handle_redis_message(message)
        except asyncio.CancelledError:
            logger.info("Redis listener cancelled")
        except Exception as e:
            logger.error(f"Error in Redis listener: {e}")
        finally:
            await pubsub.close()
    
    async def handle_redis_message(self, message: dict):
        """Handle incoming Redis Pub/Sub message"""
        try:
            # With psubscribe the actual channel is in "channel"; decode if bytes
            raw_channel = message.get("channel") or message.get("pattern", b"")
            channel = raw_channel.decode() if isinstance(raw_channel, bytes) else raw_channel

            raw_data = message["data"]
            data = json.loads(raw_data.decode() if isinstance(raw_data, bytes) else raw_data)

            # Extract job_id from channel (format: progress:{job_id})
            job_id = channel.split(":", 1)[1]

            # Broadcast to subscribed users
            if job_id in self.job_subscriptions:
                for user_id in list(self.job_subscriptions[job_id]):
                    await self.send_to_user(user_id, data)
        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to all connections for a user"""
        if user_id not in self.connections:
            return
        
        disconnected = []
        
        for websocket in self.connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected sockets
        for websocket in disconnected:
            await self.disconnect(websocket, user_id)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected users"""
        for user_id in list(self.connections.keys()):
            await self.send_to_user(user_id, message)

# Global instance
websocket_manager = WebSocketManager()
