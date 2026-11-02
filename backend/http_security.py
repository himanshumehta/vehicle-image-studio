"""HTTP hardening for an API that has no authentication and is meant to run locally.

* ``BodySizeLimitMiddleware`` rejects request bodies above a byte limit before
  they are parsed or spooled to disk.
* ``CrossSiteWriteGuard`` refuses state-changing requests that a browser marks
  as cross-site. Without it any web page the user visits could POST a form to
  ``localhost:8000`` and overwrite images or spend the user's AI-provider credit
  (``multipart/form-data`` is a CORS "simple" request, so no preflight runs).
* ``SecurityHeadersMiddleware`` adds nosniff/framing/CSP headers so a stored
  file can never be rendered as an active document.
"""
from __future__ import annotations

import json
from typing import Iterable
from urllib.parse import urlsplit

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Swagger UI loads its assets from a CDN, so the strict API CSP is not applied there.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
API_CSP = "default-src 'none'; frame-ancestors 'none'; sandbox"


async def _send_json(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        too_large = f"Request body exceeds {self.max_bytes // (1024 * 1024)} MB"
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await _send_json(send, 413, too_large)
            return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:  # chunked upload without Content-Length
                    # FastAPI re-raises HTTPExceptions from body parsing, so this becomes a 413.
                    raise HTTPException(413, too_large)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except HTTPException as exc:
            if exc.status_code != 413 or response_started:
                raise
            await _send_json(send, 413, too_large)


def is_cross_site_write(method: str, headers: dict, allowed_origins: Iterable[str]) -> bool:
    """True for a state-changing request that a browser sent from another site.

    Explicitly allowed CORS origins pass. ``Sec-Fetch-Site`` is authoritative
    when present (all current browsers send it); otherwise ``Origin`` is compared
    with ``Host``. Clients that send neither header (curl, scripts) are not
    browsers acting on someone else's behalf and pass.
    """
    if method.upper() in SAFE_METHODS:
        return False
    origin = headers.get("origin")
    if origin and origin in set(allowed_origins):
        return False
    site = headers.get("sec-fetch-site")
    if site is not None:
        return site == "cross-site"
    if not origin:
        return False
    return urlsplit(origin).netloc != headers.get("host", "")


class CrossSiteWriteGuard:
    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str]):
        self.app = app
        self.allowed_origins = list(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
            if is_cross_site_write(scope["method"], headers, self.allowed_origins):
                await _send_json(send, 403, "Cross-site request refused")
                return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        strict = not scope["path"].startswith(DOCS_PATHS)

        async def add_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                extra = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                ]
                if strict:
                    extra.append((b"content-security-policy", API_CSP.encode()))
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        await self.app(scope, receive, add_headers)
