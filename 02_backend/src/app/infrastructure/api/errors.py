from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

VALIDATION_TRACE_IDS = {
    "/api/v1/register": "users-001",
    "/api/v1/login": "users-002",
    "/api/v1/refresh-token": "users-003",
    "/api/v1/logout": "users-003",
}


class ApiError(Exception):
    def __init__(self, status_code: int, trace_id: str, message: str) -> None:
        self.status_code = status_code
        self.trace_id = trace_id
        self.message = message


def error_response(status_code: int, trace_id: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"trace_id": trace_id, "message": message})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.trace_id, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return error_response(404, "middlware-001", "rotuer not found")
        return error_response(exc.status_code, "error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        trace_id = VALIDATION_TRACE_IDS.get(request.url.path, "error")
        first = exc.errors()[0] if exc.errors() else {}
        return error_response(400, trace_id, str(first.get("msg", "invalid request")))
