import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import trace_id_var


class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        trace_id_var.set(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
