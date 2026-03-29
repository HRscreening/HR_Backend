# core/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
from src.services.errors.base import DomainError
from fastapi.exceptions import RequestValidationError
from configs.log_config import get_logger 

# core/exception_handlers.py




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




async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []

    for err in exc.errors():
        errors.append({
            "field": " -> ".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"]
        })

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation failed",
            "errors": errors
        }
    )