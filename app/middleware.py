"""
app/middleware.py
=================
FastAPI middleware stack:
  1. CORS            — allow dashboard and frontend origins
  2. Request logging — log every request with timing and request ID
  3. Error handling  — catch unhandled exceptions, return clean JSON
 
Middleware runs in this order:
  Request  → CORS → Logging → Route handler
  Response ← CORS ← Logging ← Route handler
"""

import time
import traceback
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# Request Logging Middleware

class RequestLoggingMiddleware(BaseHTTPMiddleware):
   """
    Logs every incoming request and outgoing response with:
      - request_id  : short UUID for tracing a request end-to-end
      - method      : GET, POST, etc.
      - path        : URL path
      - status_code : response status
      - duration_ms : how long the request took
    """
   
   async def dispatch(self, request:Request, call_next:Callable) -> Response:
        
        request_id=str(uuid.uuid4())[:8]
        start_time = time.perf_counter()

        request.state.request_id = request_id

        logger.info(
            "request_received",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise


        duration_ms = round((time.perf_counter() - start_time) - 1000, 2)

        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )


        response.headers["X-Request-ID"]=request_id
        response.headers["X-Responese-Time"] = f"{duration_ms}ms"

        return response

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches any unhandled exception and returns a consistent JSON error
    envelope instead of a raw 500 HTML page or stack trace.
    """

    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        traceback=traceback.format_exc(),
    )

    detail = str(exc) if settings.is_development else "An unexpected error occured."

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error":{
                "code": "INTERNAL_SERVER_ERROR",
                "message": detail,
                "requesst_id": request_id,
            },
        },
    )

def register_middleware(app:FastAPI) -> None:
    """
    Attach all middleware to the FastAPI app instance.
    Called once in main.py during app creation.
 
    Order matters — the first middleware added is the outermost layer.
    """


     # 1. CORS — must be first so browser preflight requests are handled
    app.add_middleware(
         CORSMiddleware,
         allow_origins=settings.allowed_origins_list,
         allow_credentials=True,
         allow_methods=["*"],
         allow_headers=["*"],
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_exception_handler(Exception, global_exception_handler)

