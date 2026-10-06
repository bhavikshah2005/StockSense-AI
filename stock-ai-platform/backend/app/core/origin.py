from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Reject cross-site writes from origins that are not configured.

    Browser requests include Origin. Same-origin calls, including Swagger on the
    API host, are allowed. Missing Origin is allowed so non-browser clients can
    call the API. Combined with CORS credentials, this is the CSRF control for
    the session cookie.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if request.method in _UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if origin is not None and not _origin_allowed(request, origin):
                return JSONResponse(status_code=403, content={"detail": "Origin is not allowed"})
        return await call_next(request)


def _origin_allowed(request: Request, origin: str) -> bool:
    normalized = origin.rstrip("/")
    if normalized in settings.allowed_origins:
        return True
    host = request.headers.get("host")
    if host and normalized == f"{request.url.scheme}://{host}":
        return True
    return False
