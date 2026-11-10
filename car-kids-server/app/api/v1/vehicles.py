from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request

from app.core.security import api_response, get_request_id
from app.db import db_session
from app.services.catalog_service import (
    get_vehicle_detail,
    list_random_vehicles,
    list_vehicles,
)

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("/random")
def get_random_vehicles(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    with db_session() as conn:
        data = list_random_vehicles(conn, limit=limit)
    return api_response(data=data, request_id=get_request_id(request))


@router.get("")
def get_vehicles(
    request: Request,
    category_id: Optional[int] = Query(default=None),
    brand_id: Optional[int] = Query(default=None),
    series_id: Optional[int] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    with db_session() as conn:
        data = list_vehicles(
            conn,
            category_id=category_id,
            brand_id=brand_id,
            series_id=series_id,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    return api_response(data=data, request_id=get_request_id(request))


@router.get("/{vehicle_id}")
def get_vehicle_by_id(request: Request, vehicle_id: int) -> dict:
    with db_session() as conn:
        detail = get_vehicle_detail(conn, vehicle_id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail={"code": 40401, "message": "车型不存在或尚未通过审核"},
        )
    return api_response(data=detail, request_id=get_request_id(request))

