from typing import Any, Optional
import uuid
from fastapi import Header, HTTPException, Request

from app.core.config import settings


def generate_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def api_response(
    data: Any = None,
    message: str = "ok",
    code: int = 0,
    request_id: Optional[str] = None,
) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data if data is not None else {},
        "request_id": request_id or generate_request_id(),
    }


async def verify_admin_token(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> str:
    """管理员接口鉴权：必须携带有效的 X-Admin-Token。"""
    if not x_admin_token or x_admin_token != settings.ADMIN_ACCESS_TOKEN:
        raise HTTPException(status_code=403, detail={"code": 40301, "message": "无权访问管理接口"})
    return x_admin_token


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or generate_request_id()

