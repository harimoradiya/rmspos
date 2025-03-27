from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from typing import Dict, List
from models.user import User, UserRole
from utils.auth import get_current_active_user
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime
import json

router = APIRouter(prefix="/api/v1/websocket", tags=["websocket"])

# Store active connections
class ConnectionManager:
    def __init__(self):
        # Store connections by role and user_id
        self.active_connections: Dict[str, Dict[int, WebSocket]] = {
            "kitchen": {},
            "waiter": {},
            "manager": {}
        }
    
    async def connect(self, websocket: WebSocket, role: str, user_id: int):
        await websocket.accept()
        if role in self.active_connections:
            self.active_connections[role][user_id] = websocket
    
    def disconnect(self, role: str, user_id: int):
        if role in self.active_connections:
            self.active_connections[role].pop(user_id, None)
    
    async def broadcast_to_role(self, role: str, message: dict):
        if role in self.active_connections:
            for connection in self.active_connections[role].values():
                await connection.send_json(message)
    
    async def send_to_user(self, role: str, user_id: int, message: dict):
        if role in self.active_connections and user_id in self.active_connections[role]:
            await self.active_connections[role][user_id].send_json(message)

manager = ConnectionManager()

# WebSocket endpoint
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        # Get token from query parameters
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Verify token and get user
        try:
            from utils.auth import SECRET_KEY, ALGORITHM
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_email: str = payload.get("sub")
            if user_email is None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # Get user from database
            from database import get_db
            db = next(get_db())
            user = db.query(User).filter(User.email == user_email).first()
            if not user:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # Map user role to connection type
            role_map = {
                UserRole.KITCHEN.value: "kitchen",
                UserRole.WAITER.value: "waiter",
                UserRole.MANAGER.value: "manager"
            }
            role = role_map.get(user.role)
            if not role:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # Accept connection and add to manager
            await manager.connect(websocket, role, user.id)
            
            try:
                while True:
                    # Wait for messages (heartbeat or client messages)
                    data = await websocket.receive_text()
                    try:
                        message = json.loads(data)
                        # Handle client messages if needed
                        await websocket.send_json({"status": "received"})
                    except json.JSONDecodeError:
                        continue
            except WebSocketDisconnect:
                manager.disconnect(role, user.id)
        
        except JWTError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
    except Exception as e:
        # Log the error and close connection
        print(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass

# Helper functions for other routes to send notifications
async def notify_kitchen_new_kot(kot_data: dict):
    message = {
        "event": "new_kot",
        "kot_id": kot_data["id"],
        "item": kot_data["item_name"],
        "quantity": kot_data["quantity"],
        "notes": kot_data.get("notes", ""),
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_role("kitchen", message)

async def notify_waiter_payment_complete(payment_data: dict):
    message = {
        "event": "payment_completed",
        "order_id": payment_data["order_id"],
        "table_id": payment_data["table_id"],
        "invoice_id": payment_data["invoice_id"],
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_to_role("waiter", message)

async def notify_order_status_update(order_data: dict):
    message = {
        "event": "order_status_update",
        "order_id": order_data["id"],
        "status": order_data["status"],
        "timestamp": datetime.utcnow().isoformat()
    }
    # Notify both kitchen and waiters
    await manager.broadcast_to_role("kitchen", message)
    await manager.broadcast_to_role("waiter", message)