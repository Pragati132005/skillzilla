<<<<<<< HEAD
"""Tiny JSON-over-HTTP API so the React Profile Builder (Module 3) can call Talent Check.

    GET  /health
    GET  /api/companies?q=goog&limit=20
    GET  /api/companies/<id>
    POST /api/talent-check      {"profile": {...}, "company": "Google LLC"}   or   {"profile": {...}, "company_id": 4}

Standard library only (ThreadingHTTPServer) - nothing to install, nothing to version-match.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .config import Settings, load_settings
from .errors import PayloadTooLargeError, RequestError, TalentCheckError
from .repository import DataRepository
from .service import TalentCheckService

log = logging.getLogger("talent_check")
MAX_BODY = 1_000_000  # 1 MB is far more than any profile


def make_handler(service: TalentCheckService, settings: Settings):
    allowed = set(settings.cors_origins)
    allow_all = "*" in allowed

    class Handler(BaseHTTPRequestHandler):
        server_version = "TalentCheck/1.0"

        # -- helpers ---------------------------------------------------------------
        def _cors_origin(self) -> Optional[str]:
            origin = self.headers.get("Origin")
            if allow_all:
                return "*"
            return origin if origin and origin in allowed else None

        def _send(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            origin = self._cors_origin()
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(body)

        def _error(self, exc: Exception) -> None:
            if isinstance(exc, TalentCheckError):
                self._send(exc.http_status, {"error": exc.to_dict()})
            else:
                log.exception("unhandled error")
                self._send(500, {"error": {"code": "internal_error", "message": "Unexpected server error"}})

        def log_message(self, fmt: str, *args: Any) -> None:  # quiet, never logs bodies
            log.info("%s - %s", self.address_string(), fmt % args)

        def _read_json(self) -> Dict[str, Any]:
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype and ctype != "application/json":
                raise RequestError("Content-Type must be application/json")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise RequestError("Invalid Content-Length")
            if length <= 0:
                raise RequestError("Request body is empty")
            if length > MAX_BODY:
                self.close_connection = True
                raise PayloadTooLargeError("Request body too large (max 1 MB)")
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise RequestError("Request body is not valid JSON")
            if not isinstance(data, dict):
                raise RequestError("Request body must be a JSON object")
            return data

        # -- verbs -----------------------------------------------------------------
        def do_OPTIONS(self) -> None:
            self.send_response(204)
            origin = self._cors_origin()
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Max-Age", "600")
                self.send_header("Vary", "Origin")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:
            try:
                url = urlparse(self.path)
                path = url.path.rstrip("/") or "/"
                qs = parse_qs(url.query)
                if path == "/":
                    self._send(200, {
                        "service": "RADIX Talent Match - Module 4: Talent Check",
                        "status": "running",
                        "endpoints": {
                            "GET /health": "data source + company count",
                            "GET /api/companies?q=": "list / search companies",
                            "GET /api/companies/<id>": "one company's 12 required levels",
                            "POST /api/talent-check": "body: {profile: {...}, company: 'Google'} or {profile, company_id: 4}",
                        },
                    })
                elif path == "/favicon.ico":
                    self.send_response(204)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                elif path == "/health":
                    self._send(200, {"status": "ok", **service.repo.health()})
                elif path == "/api/companies":
                    q = (qs.get("q") or [""])[0]
                    try:
                        limit = int((qs.get("limit") or ["200"])[0])
                    except ValueError:
                        raise RequestError("limit must be an integer")
                    self._send(200, service.companies(q, max(1, min(limit, 500))))
                else:
                    m = re.fullmatch(r"/api/companies/(\d+)", path)
                    if m:
                        self._send(200, service.company(company_id=int(m.group(1))))
                    else:
                        self._send(404, {"error": {"code": "not_found", "message": f"No route {path}"}})
            except Exception as exc:  # noqa: BLE001 - mapped to JSON below
                self._error(exc)

        def do_POST(self) -> None:
            try:
                path = urlparse(self.path).path.rstrip("/")
                if path != "/api/talent-check":
                    self._send(404, {"error": {"code": "not_found", "message": f"No route {path}"}})
                    return
                data = self._read_json()
                if "profile" not in data:
                    raise RequestError("Body must contain 'profile'")
                result = service.run(data["profile"], company=data.get("company"),
                                     company_id=data.get("company_id"))
                self._send(200, result)
            except Exception as exc:  # noqa: BLE001
                self._error(exc)

    return Handler


def create_server(settings: Optional[Settings] = None, service: Optional[TalentCheckService] = None,
                  host: Optional[str] = None, port: Optional[int] = None) -> ThreadingHTTPServer:
    settings = settings or load_settings()
    service = service or TalentCheckService(DataRepository(settings))
    server = ThreadingHTTPServer((host or settings.host, settings.port if port is None else port),
                                 make_handler(service, settings))
    server.daemon_threads = True
    return server


def serve(settings: Optional[Settings] = None) -> None:  # pragma: no cover - interactive
    settings = settings or load_settings()
    server = create_server(settings)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    host, port = server.server_address[:2]
    print(f"Talent Check API on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def start_in_thread(server: ThreadingHTTPServer) -> threading.Thread:
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t
=======
"""ASGI entry point retained as server.py for integration conventions."""
from .api import app
>>>>>>> 4c9d1dbefd237039dacabfd3cd53abe17201b131
