from __future__ import annotations

import json
import logging
import mimetypes
import socket
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from updater import UpdateError, apply_update, check_update, local_version

APP_NAME = "Miyori Kitsune"
APP_VERSION = local_version()
HOST = "127.0.0.1"
DEFAULT_PORT = 8765

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
CONFIG_DIR = ROOT / "config"

for directory in (DATA_DIR, LOG_DIR, CONFIG_DIR):
    directory.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "miyori-kitsune.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(APP_NAME)


def find_port(start: int = DEFAULT_PORT, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free local port was found.")


class MiyoriHandler(BaseHTTPRequestHandler):
    server_version = f"MiyoriKitsune/{APP_VERSION}"

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._json({
                "ok": True,
                "app": APP_NAME,
                "version": APP_VERSION,
                "portable": True,
                "root": str(ROOT),
                "time": int(time.time()),
            })
            return

        if parsed.path == "/api/config":
            self._json({
                "app": APP_NAME,
                "version": APP_VERSION,
                "repository": "Aspksa/Miyori-Kitsune",
                "menu": ["account", "chat", "workspace", "home", "settings", "updates", "mobile"],
            })
            return

        if parsed.path == "/api/update/check":
            try:
                self._json(check_update())
            except UpdateError as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return

        requested = parsed.path.lstrip("/") or "index.html"
        candidate = (WEB_DIR / requested).resolve()

        try:
            candidate.relative_to(WEB_DIR.resolve())
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        if not candidate.is_file():
            candidate = WEB_DIR / "index.html"

        try:
            content = candidate.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        mime, _ = mimetypes.guess_type(candidate.name)
        content_type = mime or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
            content_type += "; charset=utf-8"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/update/apply":
            self._read_json_body()
            try:
                self._json(apply_update())
            except UpdateError as exc:
                log.warning("Update failed: %s", exc)
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            except Exception:
                log.exception("Unexpected updater failure")
                self._json({"ok": False, "error": "Внутренняя ошибка обновления."}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._json({"ok": False, "error": "Unknown endpoint"}, HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


def open_browser(url: str) -> None:
    time.sleep(0.45)
    webbrowser.open(url, new=1)


def main() -> int:
    if not WEB_DIR.exists():
        log.error("Web directory not found: %s", WEB_DIR)
        return 2

    try:
        port = find_port()
        server = ThreadingHTTPServer((HOST, port), MiyoriHandler)
    except Exception:
        log.exception("Failed to initialize Miyori Kitsune core")
        return 3

    url = f"http://{HOST}:{port}/"
    log.info("%s %s started at %s", APP_NAME, APP_VERSION, url)
    log.info("Portable root: %s", ROOT)
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        log.info("Shutdown requested")
    finally:
        server.server_close()
        log.info("Core stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
