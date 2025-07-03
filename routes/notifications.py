import logging
from fastapi import WebSocket, WebSocketDisconnect,APIRouter,Depends
from typing import Dict, List
from sqlalchemy.orm import Session
from utils.database import get_db
from models.restaurant_outlet import RestaurantOutlet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}  

    async def connect(self, websocket: WebSocket, outlet_id: int):
        await websocket.accept()
        if outlet_id not in self.active_connections:
            self.active_connections[outlet_id] = []
        self.active_connections[outlet_id].append(websocket)
        logger.debug(f"WebSocket connected for outlet {outlet_id}. Total connections: {len(self.active_connections[outlet_id])}")

    def disconnect(self, websocket: WebSocket, outlet_id: int):
        if outlet_id in self.active_connections:
            self.active_connections[outlet_id].remove(websocket)
            if not self.active_connections[outlet_id]:
                del self.active_connections[outlet_id]
            logger.debug(f"WebSocket disconnected for outlet {outlet_id}. Total connections: {len(self.active_connections.get(outlet_id, []))}")

    async def broadcast(self, message: dict, outlet_id: int):
        if outlet_id in self.active_connections:
            for connection in self.active_connections[outlet_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send WebSocket message to outlet {outlet_id}: {str(e)}")

connection_manager = ConnectionManager()

async def notify_order_status_update(data: dict):
    outlet_id = data.get("outlet_id")
    if not outlet_id:
        logger.warning("No outlet_id provided in notify_order_status_update")
        return

    logger.debug(f"Sending order status update for outlet {outlet_id}: {data}")
    try:
        await connection_manager.broadcast(data, outlet_id)
    except Exception as e:
        logger.warning(f"Failed to broadcast order status update for outlet {outlet_id}: {str(e)}")

async def notify_kitchen_new_kot(data: dict):
    outlet_id = data.get("outlet_id")
    if not outlet_id:
        logger.warning("No outlet_id provided in notify_kitchen_new_kot")
        return

    logger.debug(f"Sending KOT notification for outlet {outlet_id}: {data}")
    try:
        await connection_manager.broadcast(data, outlet_id)
    except Exception as e:
        logger.warning(f"Failed to broadcast KOT notification for outlet {outlet_id}: {str(e)}")

async def notify_kot_status_update(data: dict):
    outlet_id = data.get("outlet_id")
    if not outlet_id:
        logger.warning("No outlet_id provided in notify_kot_status_update")
        return

    logger.debug(f"Sending KOT status update for outlet {outlet_id}: {data}")
    try:
        await connection_manager.broadcast(data, outlet_id)
    except Exception as e:
        logger.warning(f"Failed to broadcast KOT status update for outlet {outlet_id}: {str(e)}")

@router.websocket("/ws/{outlet_id}")
async def websocket_notifications(websocket: WebSocket, outlet_id: int, db: Session = Depends(get_db)):
    outlet = db.query(RestaurantOutlet).filter(RestaurantOutlet.id == outlet_id).first()
    if not outlet:
        await websocket.close(code=4000, reason="Invalid outlet ID")
        return

    try:
        await connection_manager.connect(websocket, outlet_id)
        while True:
            await websocket.receive_text()  
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, outlet_id)
    except Exception as e:
        logger.error(f"WebSocket error for outlet {outlet_id}: {str(e)}")
        connection_manager.disconnect(websocket, outlet_id)
        await websocket.close(code=4000, reason=str(e))

@router.post("/test-broadcast")
async def test_broadcast(data: dict):
    """
    Send a test notification to a specific outlet via WebSocket.
    Example payload:
    {
        "outlet_id": 2,
        "message": "Test message from Postman"
    }
    """
    await notify_order_status_update(data)
    return {"detail": "Broadcast sent"}
 