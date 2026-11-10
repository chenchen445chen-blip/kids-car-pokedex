from fastapi import APIRouter, Depends, Request

from app.core.security import api_response, get_request_id, verify_admin_token
from app.db import db_session
from app.schemas import (
    BrandPatchRequest,
    InboxResolveRequest,
    ReviewActionRequest,
    SeriesPatchRequest,
    VehiclePatchRequest,
)
from app.services.review_service import (
    approve_brand,
    approve_series,
    approve_vehicle,
    get_admin_vehicle_detail,
    list_pending_brands,
    list_pending_series,
    list_pending_vehicles,
    list_recognition_inbox,
    patch_brand,
    patch_series,
    patch_vehicle,
    reject_vehicle,
    resolve_recognition_inbox,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_token)],
)


@router.get("/brands/pending")
def admin_get_pending_brands(request: Request) -> dict:
    with db_session() as conn:
        items = list_pending_brands(conn)
    return api_response(data={"items": items}, request_id=get_request_id(request))


@router.patch("/brands/{brand_id}")
def admin_patch_brand(
    request: Request, brand_id: int, payload: BrandPatchRequest
) -> dict:
    with db_session() as conn:
        data = patch_brand(conn, brand_id, payload)
    return api_response(data=data, request_id=get_request_id(request))


@router.post("/brands/{brand_id}/approve")
def admin_approve_brand(
    request: Request,
    brand_id: int,
    action: ReviewActionRequest = ReviewActionRequest(),
) -> dict:
    with db_session() as conn:
        data = approve_brand(conn, brand_id, action)
    return api_response(data=data, request_id=get_request_id(request))


@router.get("/series/pending")
def admin_get_pending_series(request: Request) -> dict:
    with db_session() as conn:
        items = list_pending_series(conn)
    return api_response(data={"items": items}, request_id=get_request_id(request))


@router.patch("/series/{series_id}")
def admin_patch_series(
    request: Request, series_id: int, payload: SeriesPatchRequest
) -> dict:
    with db_session() as conn:
        data = patch_series(conn, series_id, payload)
    return api_response(data=data, request_id=get_request_id(request))


@router.post("/series/{series_id}/approve")
def admin_approve_series(
    request: Request,
    series_id: int,
    action: ReviewActionRequest = ReviewActionRequest(),
) -> dict:
    with db_session() as conn:
        data = approve_series(conn, series_id, action)
    return api_response(data=data, request_id=get_request_id(request))


@router.get("/vehicles/pending")
def admin_get_pending_vehicles(request: Request) -> dict:
    with db_session() as conn:
        items = list_pending_vehicles(conn)
    return api_response(data={"items": items}, request_id=get_request_id(request))


@router.get("/vehicles/{vehicle_id}")
def admin_get_vehicle(request: Request, vehicle_id: int) -> dict:
    with db_session() as conn:
        data = get_admin_vehicle_detail(conn, vehicle_id)
    return api_response(data=data, request_id=get_request_id(request))


@router.patch("/vehicles/{vehicle_id}")
def admin_patch_vehicle(
    request: Request, vehicle_id: int, payload: VehiclePatchRequest
) -> dict:
    with db_session() as conn:
        data = patch_vehicle(conn, vehicle_id, payload)
    return api_response(data=data, request_id=get_request_id(request))


@router.post("/vehicles/{vehicle_id}/approve")
def admin_approve_vehicle(
    request: Request,
    vehicle_id: int,
    action: ReviewActionRequest = ReviewActionRequest(),
) -> dict:
    with db_session() as conn:
        data = approve_vehicle(conn, vehicle_id, action)
    return api_response(data=data, request_id=get_request_id(request))


@router.post("/vehicles/{vehicle_id}/reject")
def admin_reject_vehicle(
    request: Request,
    vehicle_id: int,
    action: ReviewActionRequest = ReviewActionRequest(),
) -> dict:
    with db_session() as conn:
        data = reject_vehicle(conn, vehicle_id, action)
    return api_response(data=data, request_id=get_request_id(request))


@router.get("/recognition-inbox")
def admin_get_recognition_inbox(request: Request) -> dict:
    with db_session() as conn:
        items = list_recognition_inbox(conn)
    return api_response(data={"items": items}, request_id=get_request_id(request))


@router.post("/recognition-inbox/{inbox_id}/resolve")
def admin_resolve_recognition_inbox(
    request: Request, inbox_id: int, payload: InboxResolveRequest
) -> dict:
    with db_session() as conn:
        data = resolve_recognition_inbox(conn, inbox_id, payload)
    return api_response(data=data, request_id=get_request_id(request))

