from fastapi import APIRouter, HTTPException, Request

from app.core.security import api_response, get_request_id
from app.db import db_session
from app.services.series_service import get_series_detail

router = APIRouter(prefix="/series", tags=["Series"])


@router.get("/{series_id}")
def get_series_by_id(request: Request, series_id: int) -> dict:
    with db_session() as conn:
        detail = get_series_detail(conn, series_id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail={"code": 40401, "message": "车系不存在或尚未通过审核"},
        )
    return api_response(data=detail, request_id=get_request_id(request))

