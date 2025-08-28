# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import secrets, time

app = FastAPI(title="Yandex Smart Home Demo")

# --- Настройки клиента (должны совпадать с формой в Яндекс Диалогах) ---
CLIENT_ID = "my-smart-home"
CLIENT_SECRET = "supersecret123"
ACCESS_TTL = 3600  # 1 час
REFRESH_TTL = 30 * 24 * 3600  # 30 дней

# --- Память «для демо» (в проде замени на БД) ---
auth_codes = {}  # code -> {user_id, client_id, exp, redirect_uri}
access_tokens = {}  # access_token -> {user_id, client_id, exp, refresh_token}
refresh_tokens = {}  # refresh_token -> {user_id, client_id, exp}
device_state = {}  # user_id -> {"relay_1": {"on": bool}}


# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], allow_credentials=True,
#     allow_methods=["*"], allow_headers=["*"],
# )

# --------- ВСПОМОГАТЕЛЬНЫЕ ---------
def now() -> int: return int(time.time())


def require_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return auth.split(" ", 1)[1].strip()


def user_by_token(token: str) -> str:
    t = access_tokens.get(token)
    if not t or t["exp"] < now():
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    return t["user_id"]


def ensure_user_initialized(user_id: str):
    device_state.setdefault(user_id, {"relay_1": {"on": False}})

@app.get('/')
async def welcome():
    return {'message': 'Hello, world!'}
@app.get("/v1.0")
async def root_v1():
    return {"status": "ok"}

# --------- OAUTH2: /authorize ---------
@app.get("/authorize")
async def authorize(request: Request):
    """
    Имитация страницы логина/согласия.
    При первом заходе покажет простую форму (ввести имя пользователя).
    После «входа» редиректит обратно в redirect_uri с code (+state, если был).
    """
    q = dict(request.query_params)
    client_id = q.get("client_id")
    redirect_uri = '/'
    state = q.get("state")
    response_type = q.get("response_type", "code")

    if client_id != CLIENT_ID or response_type != "code" or not redirect_uri:
        raise HTTPException(status_code=400, detail="Bad authorize request")

    username = q.get("user")  # для демо можно сразу передать ?user=shohruh
    if not username:
        # Простая HTML-форма «входа»
        html = f"""
        <html><body style="font-family: sans-serif">
          <h2>Вход в аккаунт устройства</h2>
          <form method="get" action="/authorize">
            <input type="hidden" name="client_id" value="{client_id}">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <input type="hidden" name="state" value="{state or ''}">
            <input type="hidden" name="response_type" value="code">
            <label>Имя пользователя:</label>
            <input name="user" placeholder="shohruh" required>
            <button type="submit">Войти и выдать код</button>
          </form>
        </body></html>
        """
        return HTMLResponse(html)

    # «Логин успешен» -> выдаём одноразовый code
    code = secrets.token_urlsafe(24)
    auth_codes[code] = {
        "user_id": username,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "exp": now() + 600,  # 10 минут
    }
    sep = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{sep}code={code}" + (f"&state={state}" if state else "")
    return RedirectResponse(location, status_code=302)


# --------- OAUTH2: /token + /token/refresh ---------
@app.post("/token")
async def token(request: Request):
    form = dict(await request.form())
    grant_type = form.get("grant_type")
    client_id = form.get("client_id")
    client_secret = form.get("client_secret")

    if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
        raise HTTPException(status_code=401, detail="Invalid client")

    if grant_type == "authorization_code":
        code = form.get("code")
        data = auth_codes.pop(code, None)
        if not data or data["exp"] < now():
            raise HTTPException(status_code=400, detail="Invalid or expired code")

        user_id = data["user_id"]
        ensure_user_initialized(user_id)
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        access_tokens[access] = {
            "user_id": user_id, "client_id": client_id,
            "exp": now() + ACCESS_TTL, "refresh_token": refresh
        }
        refresh_tokens[refresh] = {
            "user_id": user_id, "client_id": client_id,
            "exp": now() + REFRESH_TTL
        }
        return JSONResponse({
            "token_type": "bearer",
            "access_token": access,
            "expires_in": ACCESS_TTL,
            "refresh_token": refresh,
            "scope": "devices"
        })

    elif grant_type == "refresh_token":
        # допускаем refresh и тут (на случай если Яндекс будет слать сюда)
        refresh = form.get("refresh_token")
        info = refresh_tokens.get(refresh)
        if not info or info["exp"] < now():
            raise HTTPException(status_code=400, detail="Invalid or expired refresh_token")

        user_id = info["user_id"]
        access = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)
        access_tokens[access] = {
            "user_id": user_id, "client_id": client_id,
            "exp": now() + ACCESS_TTL, "refresh_token": new_refresh
        }
        refresh_tokens[new_refresh] = {
            "user_id": user_id, "client_id": client_id,
            "exp": now() + REFRESH_TTL
        }
        return JSONResponse({
            "token_type": "bearer",
            "access_token": access,
            "expires_in": ACCESS_TTL,
            "refresh_token": new_refresh,
            "scope": "devices"
        })

    else:
        raise HTTPException(status_code=400, detail="Unsupported grant_type")


@app.post("/token/refresh")
async def token_refresh(request: Request):
    form = dict(await request.form())
    client_id = form.get("client_id")
    client_secret = form.get("client_secret")
    refresh = form.get("refresh_token")

    if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
        raise HTTPException(status_code=401, detail="Invalid client")

    info = refresh_tokens.get(refresh)
    if not info or info["exp"] < now():
        raise HTTPException(status_code=400, detail="Invalid or expired refresh_token")

    user_id = info["user_id"]
    access = secrets.token_urlsafe(32)
    new_refresh = secrets.token_urlsafe(32)
    access_tokens[access] = {
        "user_id": user_id, "client_id": client_id,
        "exp": now() + ACCESS_TTL, "refresh_token": new_refresh
    }
    refresh_tokens[new_refresh] = {
        "user_id": user_id, "client_id": client_id,
        "exp": now() + REFRESH_TTL
    }
    return JSONResponse({
        "token_type": "bearer",
        "access_token": access,
        "expires_in": ACCESS_TTL,
        "refresh_token": new_refresh,
        "scope": "devices"
    })


# --------- Проверка токена (иногда Яндекс дергает) ---------
@app.get("/user/info")
async def user_info(request: Request):
    token = require_bearer(request)
    uid = user_by_token(token)
    return {"user_id": uid}


# --------- SMART HOME ---------
@app.post("/v1.0/user/devices")
async def devices(request: Request):
    token = require_bearer(request)
    uid = user_by_token(token)
    ensure_user_initialized(uid)
    return {
        "request_id": secrets.token_hex(8),
        "payload": {
            "user_id": uid,
            "devices": [
                {
                    "id": "relay_1",
                    "name": "Свет в комнате",
                    "type": "devices.types.switch",
                    "capabilities": [
                        {
                            "type": "devices.capabilities.on_off",
                            "retrievable": True
                        }
                    ]
                }
            ]
        }
    }


@app.post("/v1.0/user/devices/query")
async def devices_query(request: Request):
    token = require_bearer(request)
    uid = user_by_token(token)
    ensure_user_initialized(uid)
    body = await request.json()
    result = []
    for d in body.get("devices", []):
        dev_id = d.get("id")
        if dev_id == "relay_1":
            result.append({
                "id": "relay_1",
                "capabilities": [
                    {
                        "type": "devices.capabilities.on_off",
                        "state": {"instance": "on", "value": device_state[uid]["relay_1"]["on"]}
                    }
                ]
            })
    return {"request_id": secrets.token_hex(8), "payload": {"devices": result}}


@app.post("/v1.0/user/devices/action")
async def devices_action(request: Request):
    token = require_bearer(request)
    uid = user_by_token(token)
    ensure_user_initialized(uid)
    body = await request.json()
    result = []
    for d in body.get("payload", {}).get("devices", []):
        dev_id = d.get("id")
        caps = []
        if dev_id == "relay_1":
            for c in d.get("capabilities", []):
                if c.get("type") == "devices.capabilities.on_off":
                    val = bool(c.get("state", {}).get("value"))
                    device_state[uid]["relay_1"]["on"] = val
                    caps.append({
                        "type": "devices.capabilities.on_off",
                        "state": {
                            "instance": "on",
                            "action_result": {"status": "DONE"}
                        }
                    })
            result.append({"id": "relay_1", "capabilities": caps})
    return {"request_id": secrets.token_hex(8), "payload": {"devices": result}}


@app.post("/v1.0/user/unlink")
async def unlink(request: Request):
    # Здесь можно очистить привязку (по токену определить user_id и удалить состояние)
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"ok": True}
