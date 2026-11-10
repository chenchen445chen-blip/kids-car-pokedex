from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request

from app.core.security import api_response, get_request_id
from app.db import db_session
from app.services.brand_service import (
    get_brand_detail,
    list_brand_series,
    list_brands,
)

router = APIRouter(prefix="/brands", tags=["Brands"])


@router.get("")
def get_brands(
    request: Request,
    keyword: Optional[str] = Query(default=None),
    brand_group: Optional[str] = Query(default=None),
    parent_brand_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict:
    with db_session() as conn:
        data = list_brands(
            conn,
            keyword=keyword,
            brand_group=brand_group,
            parent_brand_id=parent_brand_id,
            page=page,
            page_size=page_size,
        )
    return api_response(data=data, request_id=get_request_id(request))


@router.get("/{brand_id}")
def get_brand_by_id(request: Request, brand_id: int) -> dict:
    with db_session() as conn:
        detail = get_brand_detail(conn, brand_id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail={"code": 40401, "message": "品牌不存在或尚未通过审核"},
        )
    return api_response(data=detail, request_id=get_request_id(request))


@router.get("/{brand_id}/series")
def get_series_under_brand(
    request: Request,
    brand_id: int,
    parent_series_id: Optional[int] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
) -> dict:
    with db_session() as conn:
        data = list_brand_series(
            conn,
            brand_id=brand_id,
            parent_series_id=parent_series_id,
            keyword=keyword,
        )
    return api_response(data=data, request_id=get_request_id(request))

