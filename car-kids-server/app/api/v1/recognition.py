from io import BytesIO
from typing import Optional
import uuid
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.core.config import settings
from app.core.security import api_response, get_request_id
from app.db import db_session
from app.providers import get_recognition_provider
from app.services.draft_service import process_recognition_result

router = APIRouter(prefix="/recognition", tags=["Recognition"])

FORMAT_MIME_MAP = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def _detect_image_format(raw_bytes: bytes) -> Optional[str]:
    try:
        from PIL import Image

        with Image.open(BytesIO(raw_bytes)) as img:
            img.verify()
        with Image.open(BytesIO(raw_bytes)) as img:
            return (img.format or "").upper()
    except ImportError:
        if raw_bytes.startswith(b"\xff\xd8\xff"):
            return "JPEG"
        if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "PNG"
        if raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP":
            return "WEBP"
        return None
    except Exception:
        return None


@router.post("")
async def recognize_vehicle_image(
    request: Request,
    image: UploadFile = File(...),
    language: str = Form(default="zh-CN"),
    client_request_id: Optional[str] = Form(default=None),
    hint_keyword: Optional[str] = Form(default=None),
) -> dict:
    """
    拍照识车接口（遵循需求文档 3.3 与 6.11）：
    1. 校验上传图片大小、真实解码格式（防止伪装扩展名），在内存中处理，默认不永久留存用户原图。
    2. 调用第三方识别适配器获取候选。
    3. 按品牌 -> 车系 -> 具体车型逐级与 SQLite 本地已审核数据比对或自动创建待审核草稿。
    """
    req_id = client_request_id or f"req_{uuid.uuid4().hex[:12]}"
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=400,
            detail={"code": 40003, "message": "上传的图片文件为空"},
        )
    if len(raw_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail={"code": 40002, "message": f"图片大小超过 {settings.MAX_UPLOAD_SIZE_MB}MB 限制"},
        )

    real_format = _detect_image_format(raw_bytes)
    if not real_format:
        raise HTTPException(
            status_code=400,
            detail={"code": 40003, "message": "图片无法解析，请重新拍摄"},
        )

    real_mime = FORMAT_MIME_MAP.get(real_format)
    if not real_mime or real_mime not in settings.allowed_mime_set:
        raise HTTPException(
            status_code=400,
            detail={"code": 40001, "message": "图片格式不支持，请选择 JPG/PNG/WEBP 图片"},
        )

    provider = get_recognition_provider()
    effective_hint = hint_keyword or (image.filename or "")

    try:
        provider_result = await provider.recognize(
            image_bytes=raw_bytes,
            mime_type=real_mime,
            hint_keyword=effective_hint,
        )
    except Exception:
        return api_response(
            code=0,
            message="provider_error",
            data={
                "status": "provider_error",
                "child_message": "识车小助手暂时休息啦，我们可以先去逛逛汽车图鉴！",
            },
            request_id=get_request_id(request),
        )

    with db_session() as conn:
        outcome = process_recognition_result(
            conn=conn,
            request_id=req_id,
            provider_result=provider_result,
        )

    status_msg_map = {
        "matched": "matched",
        "pending_review": "new_vehicle_pending_review",
        "candidates": "multiple_candidates",
        "unrecognized": "unrecognized",
    }

    return api_response(
        code=0,
        message=status_msg_map.get(outcome.get("status", ""), "ok"),
        data=outcome,
        request_id=get_request_id(request),
    )

