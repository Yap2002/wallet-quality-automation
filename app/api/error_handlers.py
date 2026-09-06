import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.application.exceptions import ApplicationError
from app.domain.exceptions import DomainError

logger = logging.getLogger(__name__)


def _error_body(
    request: Request,
    code: str,
    message: str,
    details: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details,
        "trace_id": getattr(request.state, "trace_id", None),
    }


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def handle_application_error(
        request: Request,
        error: ApplicationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=_error_body(
                request,
                error.code,
                error.message,
                error.details,
            ),
        )

    @application.exception_handler(DomainError)
    async def handle_domain_error(
        request: Request,
        error: DomainError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body(
                request,
                "INVALID_DOMAIN_VALUE",
                str(error),
                {},
            ),
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body(
                request,
                "REQUEST_VALIDATION_FAILED",
                "request data is invalid",
                jsonable_encoder(error.errors()),
            ),
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        logger.exception(
            "unexpected request failure trace_id=%s",
            getattr(request.state, "trace_id", None),
            exc_info=error,
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(
                request,
                "INTERNAL_SERVER_ERROR",
                "an unexpected error occurred",
                {},
            ),
        )
