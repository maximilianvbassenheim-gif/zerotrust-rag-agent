"""Zero-Trust-Bausteine: API-Key-Prüfung, Rate-Limiting, Security-Header, Secret-Redaktion.

Grundsätze:
- Kein Vertrauen per Default: Auth wird pro Request geprüft, nicht pro Sitzung angenommen.
- Secrets werden vor dem Persistieren im Wissensspeicher redigiert.
- Konstante Zeit beim Key-Vergleich (hmac.compare_digest) gegen Timing-Angriffe.
"""

import hmac
import re
import threading
import time
from collections import deque

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .config import settings

# --- Secret-Redaktion -------------------------------------------------------

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")),
    ("google-key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("slack-token", re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("openai-proj-key", re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{40,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]


def redact_secrets(text: str) -> str:
    """Ersetzt bekannte Secret-Muster, bevor Inhalte im lokalen Speicher landen."""
    for label, pattern in SECRET_PATTERNS:
        text = pattern.sub(f"[REDACTED:{label}]", text)
    return text


# --- API-Key-Prüfung ---------------------------------------------------------


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = settings.app_api_key
    if not expected:
        return
    # Byte-Vergleich: verhindert TypeError (→ 500) bei Nicht-ASCII-Headern
    if not x_api_key or not hmac.compare_digest(
        x_api_key.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Ungültiger oder fehlender API-Key (Header: X-API-Key).",
        )


# --- Rate-Limiting (Sliding Window, in-memory) --------------------------------


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, client_id: str) -> bool:
        limit = settings.rate_limit_per_minute
        now = time.monotonic()
        with self._lock:
            window = self._hits.setdefault(client_id, deque())
            while window and now - window[0] > 60.0:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(now)
            return True


_rate_limiter = RateLimiter()


async def rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    if not _rate_limiter.check(client):
        raise HTTPException(
            status_code=429,
            detail="Rate-Limit erreicht. Bitte kurz warten und erneut versuchen.",
        )


# --- Middleware ---------------------------------------------------------------

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
        "style-src 'self'; script-src 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        length = request.headers.get("content-length")
        if length is None:
            # Chunked-Encoding ohne Content-Length würde das Limit umgehen — ablehnen.
            if request.method in ("POST", "PUT", "PATCH"):
                return JSONResponse(
                    status_code=411,
                    content={"detail": "Content-Length erforderlich."},
                )
            return await call_next(request)
        try:
            if int(length) > settings.max_request_bytes:
                return JSONResponse(status_code=413, content={"detail": "Request zu groß."})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Ungültiger Content-Length."})
        return await call_next(request)
