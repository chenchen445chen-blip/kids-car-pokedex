from typing import Optional
from fastapi import APIRouter, Query, Request

from app.core.security import api_response, get_request_id
from app.db import db_session
from app.services.category_service import list_categories

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("")
def get_categories(
    request: Request,
    parent_id: Optional[int] = Query(default=None),
    include_count: bool = Query(default=True),
    tree: bool = Query(default=True),
) -> dict:
    with db_session() as conn:
        items = list_categories(
            conn,
            parent_id=parent_id,
            include_count=include_count,
            tree=tree,
        )
    return api_response(
        data={"items": items},
        request_id=get_request_id(request),
    )

