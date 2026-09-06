import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from app.api.channel import router as channel_router
from app.api.error_handlers import register_error_handlers
from app.api.fees import router as fees_router
from app.api.health import router as health_router
from app.api.transactions import router as transactions_router
from app.api.transfers import router as transfers_router
from app.api.users import router as users_router
from app.api.wallets import router as wallets_router
from app.config import settings
from app.observability import configure_application_logging

logger = logging.getLogger("wallet.http")
WEB_ROOT = Path(__file__).resolve().parent / "web"


def create_app() -> FastAPI:
    """Create the FastAPI application and register its routes."""
    configure_application_logging()
    application = FastAPI(title=settings.app_name)
    application.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")

    @application.get("/wallet", include_in_schema=False)
    def wallet_console() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")

    @application.middleware("http")
    async def attach_trace_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        supplied_trace_id = request.headers.get("X-Trace-ID", "").strip()
        trace_id = supplied_trace_id if 0 < len(supplied_trace_id) <= 64 else uuid4().hex
        request.state.trace_id = trace_id
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request failed unexpectedly",
                extra={
                    "event": "http_request_failed",
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )
            raise
        response.headers["X-Trace-ID"] = trace_id
        logger.info(
            "request completed",
            extra={
                "event": "http_request_completed",
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        return response

    register_error_handlers(application)
    application.include_router(health_router)
    application.include_router(users_router)
    application.include_router(wallets_router)
    application.include_router(fees_router)
    application.include_router(transfers_router)
    application.include_router(transactions_router)
    application.include_router(channel_router)
    return application


app = create_app()
