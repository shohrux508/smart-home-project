import time

from fastapi import HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict
from pyee.asyncio import AsyncIOEventEmitter
from starlette.requests import Request

event_bus = AsyncIOEventEmitter()

CLIENT_ID = "my-smart-home"
CLIENT_SECRET = "supersecret123"
ACCESS_TTL = 3600  # 1 час
REFRESH_TTL = 30 * 24 * 3600  # 30 дней

# --- Память «для демо» (в проде замени на БД) ---
auth_codes = {}  # code -> {user_id, client_id, exp, redirect_uri}
access_tokens = {}  # access_token -> {user_id, client_id, exp, refresh_token}
refresh_tokens = {}  # refresh_token -> {user_id, client_id, exp}
device_state = {}  # user_id -> {"relay_1": {"on": bool}}

# ====== ВНУТРЕННЕЕ "ЯДРО" (мок) ======
# Один пользователь и одно устройство-реле
DB = {
    "users": {"user-1": {"id": "user-1", "name": "Demo User"}},
    "devices": {
        "socket-1": {
            "id": "socket-1",
            "owner_id": "user-1",
            "name": "Розетка",
            "kind": "relay",  # твой внутренний тип
            "capabilities": ["on_off"],  # твой внутренний список
            "state": {"on": False},  # текущее состояние
        }
    },
    "tokens": {"alice-demo": "user-1"},  # маппинг токена Алисы -> user_id
}


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


# Настройка логирования

class LoggingSettings(BaseSettings):
    telegram_enabled: bool = True
    telegram_log_bot_token: str = ""
    telegram_chat_id: str = ""
    level: str = "INFO"
    log_to_console: bool = True
    log_to_file: bool = False
    log_file_path: str = "logs/app.log"
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 3
    formatter: str = "[%(asctime)s] [server] [%(levelname)s] %(message)s (%(filename)s:%(lineno)d)"
    telegram_formatter: str = "[%(levelname)s] [server] %(message)s (%(filename)s:%(lineno)d)"
    model_config = SettingsConfigDict(
        env_file="../.env",  # путь до вашего .env
        env_file_encoding="utf-8",  # кодировка .env
        extra='ignore'
    )
