import uuid
from typing import Dict, Any, List

from fastapi import FastAPI, Depends
from starlette.websockets import WebSocket

from discovery_check import router as r1
from auth_module import router as r2, auth_yandex

app = FastAPI(title="Sh_IoT - Система интернет вещей")

app.include_router(r1)
app.include_router(r2)


# ====== МАППИНГ: твои модели -> формат Алисы ======
def map_kind_to_y_type(kind: str) -> str:
    # Простейшее сопоставление для демо
    if kind == "relay":
        return "devices.types.light"  # можно и switch; выберем light для наглядности
    return "devices.types.other"


def map_caps_to_y_caps(caps: List[str]) -> List[Dict[str, Any]]:
    out = []
    for c in caps:
        if c == "on_off":
            out.append({"type": "devices.capabilities.on_off"})
    return out


def to_yandex_device(device: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": device["id"],
        "name": device["name"],
        "type": map_kind_to_y_type(device["kind"]),
        "capabilities": map_caps_to_y_caps(device["capabilities"]),
    }


def to_yandex_state(device: Dict[str, Any]) -> Dict[str, Any]:
    caps = []
    if "on_off" in device["capabilities"]:
        caps.append({
            "type": "devices.capabilities.on_off",
            "state": {"instance": "on", "value": bool(device["state"].get("on", False))}
        })
    return {"id": device["id"], "capabilities": caps}


def req_id() -> str:
    return str(uuid.uuid4())


ws_session = {}


@app.websocket('/ws/{device_id}/connect')
async def device_websocket_handler(ws: WebSocket, device_id: int):
    await ws.accept()
    ws_session[2] = ws
    await ws_session[2].send_json(data={'action': 'turn_on'})
    print('Розетка в сети')
    while True:
        msg = await ws.receive_text()
        print(msg)


@app.get("/v1.0/user/devices")
async def list_devices(user=Depends(auth_yandex)):
    # Вернём все устройства юзера
    devices = [
        to_yandex_device(d)
        for d in DB["devices"].values()
        if d["owner_id"] == user["id"]
    ]
    return {"request_id": req_id(), "payload": {"user_id": user["id"], "devices": devices}, "user_id": user["id"], }


@app.post("/v1.0/user/devices/query")
async def query_devices(body: Dict[str, Any], user=Depends(auth_yandex)):
    ids = [d["id"] for d in body.get("devices", [])]
    devices = []
    for dev_id in ids:
        d = DB["devices"].get(dev_id)
        if d and d["owner_id"] == user["id"]:
            devices.append(to_yandex_state(d))
    return {"request_id": req_id(), "payload": {"devices": devices}}


@app.post("/v1.0/user/devices/action")
async def action_devices(body: Dict[str, Any], user=Depends(auth_yandex)):
    results = []
    print(body)
    for dev in body.get("payload", {}).get("devices", []):
        dev_id = dev["id"]
        d = DB["devices"].get(dev_id)
        if not d or d["owner_id"] != user["id"]:
            # По спецификации лучше вернуть ошибку по устройству
            results.append({"id": dev_id, "error_code": "DEVICE_NOT_FOUND"})
            continue

        caps_results = []
        for cap in dev.get("capabilities", []):
            ctype = cap.get("type", "")
            state = cap.get("state", {})
            state_value = state.get('value')
            if state_value:
                data = {'action': 'turn_on'}
                print('Розетка включена')

            else:
                print('Розетка выключена')
                data = {'action': 'turn_off'}

            await ws_session[2].send_json(data=data)

            if ctype == "devices.capabilities.on_off":
                value = bool(state.get("value"))
                d["state"]["on"] = value
                caps_results.append({"type": ctype, "state": {"instance": "on", "action_result": {"status": "DONE"}}})
            else:
                caps_results.append(
                    {"type": ctype, "state": {"action_result": {"status": "ERROR", "error_code": "NOT_SUPPORTED"}}})

        results.append({"id": dev_id, "capabilities": caps_results})

    return {"request_id": req_id(), "payload": {"devices": results}}


@app.post("/v1.0/user/unlink")
async def unlink(user=Depends(auth_yandex)):
    # В реальности помечаешь интеграцию как revoked
    return {"status": "ok"}
