from fastapi import APIRouter

from app.api.v1 import (
    admin,
    brands,
    categories,
    images,
    recognition,
    series,
    vehicles,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(categories.router)
api_v1_router.include_router(brands.router)
api_v1_router.include_router(series.router)
api_v1_router.include_router(vehicles.router)
api_v1_router.include_router(images.router)
api_v1_router.include_router(recognition.router)
api_v1_router.include_router(admin.router)

