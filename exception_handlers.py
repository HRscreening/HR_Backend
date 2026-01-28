# core/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
from services.errors.base import DomainError
from configs.log_config import get_logger 

logger = get_logger(__name__)

async def domain_exception_handler(
    request: Request,
    exc: DomainError,
):
    logger.warning(
        "Domain error",
        extra={
            "path": request.url.path,
            "code": exc.code,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "code": exc.code,
        },
    )
