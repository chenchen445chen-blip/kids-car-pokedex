from contextlib import asynccontextmanager
import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.security import api_response, generate_request_id, get_request_id
from app.db import initialize_database, utc_now_iso

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("car_kids_server")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("正在初始化 SQLite 数据库与 P0 图鉴种子数据...")
    initialize_database()
    logger.info("数据库与本地图片资源准备就绪。")
    yield


app = FastAPI(
    title="儿童汽车认知与拍照识别 App 后端服务",
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_ORIGINS != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    req_id = generate_request_id()
    request.state.request_id = req_id
    start_ts = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start_ts) * 1000
    response.headers["X-Request-Id"] = req_id
    logger.info(
        "%s %s -> %d (%.1f ms) [%s]",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        req_id,
    )
    return response


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", exc.status_code)
        msg = detail.get("message", "请求错误")
    else:
        code = exc.status_code
        msg = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=api_response(
            data={},
            message=msg,
            code=code,
            request_id=get_request_id(request),
        ),
    )


@app.get("/api/v1/health", tags=["Health"])
def health_check(request: Request) -> dict:
    """健康检查接口：不暴露本机磁盘绝对路径或敏感密钥。"""
    return api_response(
        data={
            "status": "healthy",
            "version": "1.2.0",
            "environment": settings.APP_ENV,
            "timestamp": utc_now_iso(),
        },
        request_id=get_request_id(request),
    )


app.include_router(api_v1_router)

