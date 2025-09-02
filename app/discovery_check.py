from fastapi import APIRouter
from starlette.requests import Request

from config import require_bearer, user_by_token

router = APIRouter()


@router.get("/v1.0/user/devices", tags=['check'])
async def unlink():
    return {"status": "ok"}


@router.get("/v1.0/user/devices/action")
async def unlink():
    return {"status": "ok"}


@router.get("/v1.0/user/devices/query")
async def unlink():
    return {"status": "ok"}


@router.get("/v1.0/")
async def unlink():
    # В реальности помечаешь интеграцию как revoked
    return {"status": "ok"}


@router.get('/v1.0/health')
async def check():
    return {'status': 'ok'}

@router.get("/user/info")
async def user_info(request: Request):
    token = require_bearer(request)
    uid = user_by_token(token)
    return {"user_id": uid}