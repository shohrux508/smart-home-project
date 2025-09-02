from fastapi import WebSocket
from app.logger_module.utils import get_logger_factory
from config import event_bus

get_logger = get_logger_factory(__name__)
logger = get_logger()


class DeviceWebSocketManager:
    def __init__(self):
        self.active: dict[int, WebSocket] = {}

    async def add(self, device_id: int, ws: WebSocket):
        self.active[device_id] = ws
        event_bus.emit('device_ws_connected', device_id, ws)

    async def remove(self, device_id: int):
        try:
            event_bus.emit("device_ws_disconnected", device_id)
            await self.active.pop(device_id, None).close()
        except Exception as e:
            pass

    async def send_personal(self, device_id: int, data: str | dict) -> dict | None | bool:
        ws = self.active.get(device_id)
        if ws:
            event_bus.emit('device_message_send', device_id, data)
            await ws.send_json(data)
        else:
            event_bus.emit('device_message_failed', device_id, data)


device_ws_manager = DeviceWebSocketManager()