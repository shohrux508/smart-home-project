from fastapi import WebSocket
from config import event_bus


@event_bus.on('device_ws_connected')
async def handle_connection(device_id, ws: WebSocket):
    await ws.send_json({'message': 'Вы подключились'})


@event_bus.on('device_ws_disconnected')
async def handle_disconnection(device_id):
    event_bus.emit('device_status', device_id, False)


@event_bus.on('device_ws_timeout')
async def handle_timeout(ws: WebSocket):
    await ws.send_json({'message': 'Время ожидания истекло!'})


@event_bus.on('device_ws_wrong_auth_token')
async def handle_device_wrong_auth_token(ws: WebSocket):
    await ws.send_json({'message': 'Неверный auth_token'})
