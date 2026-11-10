from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.db import db_session
from app.services.image_service import resolve_approved_image_file

router = APIRouter(prefix="/images", tags=["Images"])

FAST_CACHE_DIR = settings.STORAGE_ROOT / "catalog" / "fast_cache"
IMMUTABLE_CACHE_HEADERS = {"Cache-Control": "public, max-age=604800, immutable"}


@router.get("/{image_id}")
def get_image_file(image_id: int) -> FileResponse:
    # 优先直接命中预压缩极速缓存（平均 28KB/张，无需每次查库与传大图）
    fast_jpg = FAST_CACHE_DIR / f"{image_id}.jpg"
    if fast_jpg.is_file():
        return FileResponse(
            path=str(fast_jpg),
            media_type="image/jpeg",
            headers=IMMUTABLE_CACHE_HEADERS,
        )
    fast_png = FAST_CACHE_DIR / f"{image_id}.png"
    if fast_png.is_file():
        return FileResponse(
            path=str(fast_png),
            media_type="image/png",
            headers=IMMUTABLE_CACHE_HEADERS,
        )

    with db_session() as conn:
        resolved = resolve_approved_image_file(conn, image_id)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail={"code": 40401, "message": "图片不存在或未通过审核"},
        )
    file_path, mime_type = resolved
    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        headers=IMMUTABLE_CACHE_HEADERS,
    )


