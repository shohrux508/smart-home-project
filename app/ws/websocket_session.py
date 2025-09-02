import asyncio
import time
from fastapi import status
from fastapi.websockets import WebSocket, WebSocketDisconnect

from app.logger_module.utils import get_logger_factory
from config import event_bus
from app.ws.websocket_manager import device_ws_manager

get_logger = get_logger_factory(__name__)
logger = get_logger()


device_last_pong = {}


async def verify_auth_token(token):
    auth_token = 'abc123'
    return token == auth_token


class DeviceWebSocketSession:
    async def handle(self, ws: WebSocket, device_id: int):
        if not await self._authenticate(ws, device_id):
            event_bus.emit('device_ws_wrong_auth_token', ws)
            await asyncio.sleep(3)
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        await device_ws_manager.add(device_id, ws)

        device_last_pong[device_id] = time.monotonic()
        listen_task = asyncio.create_task(self._listen(ws, device_id))
        ping_task = asyncio.create_task(self.ping_pong(ws, device_id))
        try:
            await listen_task
        finally:
            ping_task.cancel()
            await device_ws_manager.remove(device_id)

    @staticmethod
    async def _authenticate(ws: WebSocket, device_id: int) -> bool:
        try:
            data = await asyncio.wait_for(ws.receive_json(), timeout=15)
        except asyncio.TimeoutError:
            event_bus.emit('device_ws_timeout', ws)
            return False

        token = data.get("auth_token") if isinstance(data, dict) else None
        verified = await verify_auth_token(token)
        return verified

    @staticmethod
    async def ping_pong(ws: WebSocket, device_id):

        while True:
            await ws.send_text("ping")
            last = device_last_pong.get(device_id)
            now = time.monotonic()

            if last is None or (now - last > 10):
                logger.warning(f"[PING] No pong from {device_id} for >10s")
                await device_ws_manager.remove(device_id)
                break
            await asyncio.sleep(5)

    @staticmethod
    async def _listen(ws: WebSocket, device_id: int):
        try:
            while True:
                msg = await ws.receive_text()
                if msg.strip().lower() == "pong":
                    device_last_pong[device_id] = time.monotonic()
                    continue
                event_bus.emit("message_from_device", device_id, msg)
        except (asyncio.CancelledError, WebSocketDisconnect):
            await device_ws_manager.remove(device_id)
        except Exception as e:
            logger.exception(f"[{device_id}] Device WS error : {e}")
            await device_ws_manager.remove(device_id)


device_ws_session = DeviceWebSocketSession()