import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import request_id_var

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        token = request_id_var.set(req_id)

        start = time.monotonic()
        try:
            response = await call_next(request)
            elapsed = round((time.monotonic() - start) * 1000)
            logger.info(
                "%s %s → %d (%dms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed,
            )
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_var.reset(token)
