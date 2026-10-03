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
from urllib.parse import parse_qs, urlparse

from account import create_pairing, get_profile, list_devices, pairing_status, revoke_device, save_profile
from cloudru import CloudRuError, credentials_status as cloudru_status, job_history as cloudru_job_history, list_training_configs as cloudru_training_configs, save_credentials as save_cloudru_credentials, submit_training_job as cloudru_submit_training_job, test_connection as cloudru_test_connection
from training_data import build_dataset as build_training_dataset, list_datasets as list_training_datasets
from assistant_gateway import build_context, capability_manifest, execute_action, state_snapshot
from brain import create_session as brain_create_session, delete_session as brain_delete_session, get_session as brain_get_session, list_sessions as brain_list_sessions, rename_session as brain_rename_session, status as brain_status, think as brain_think
from brain_architecture import architecture_state, consolidate_now, overview_state
from model_evaluation import evaluate_model as evaluate_brain_model, latest_reports as model_evaluation_reports
from model_registry import list_models as list_brain_models, summary as model_registry_summary
from neural_runtime import runtime_status as neural_runtime_status
from semantic_memory import status as semantic_memory_status
from brain_scheduler import start as start_brain_scheduler, stop as stop_brain_scheduler
from self_development import list_proposals, propose as propose_development, transition as transition_development
from entities import (
    audit_log,
    create_project,
    create_task,
    delete_project,
    delete_task,
    get_project,
    get_task,
    list_projects,
    list_tasks,
    update_project,
    update_task,
)
from memory import active_context, add_memory, delete_memory, get_memory, set_category_enabled
from updater import (
    UpdateError,
    check_update,
    download_mobile_client,
    local_manifest,
    local_version,
    mobile_update_status,
    start_update,
    update_history,
    update_progress,
)

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
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/health":
            self._json({
                "ok": True,
                "app": APP_NAME,
                "version": APP_VERSION,
                "components": local_manifest().get("components", {}),
                "portable": True,
                "root": str(ROOT),
                "time": int(time.time()),
            })
            return

        if parsed.path == "/api/config":
            self._json({
                "app": APP_NAME,
                "version": APP_VERSION,
                "components": local_manifest().get("components", {}),
                "repository": "Aspksa/Miyori-Kitsune",
                "menu": ["account", "chat", "workspace", "home", "settings", "updates", "mobile"],
            })
            return

        if parsed.path == "/api/memory":
            self._json({"ok": True, **get_memory(), "active_context": active_context()})
            return

        if parsed.path == "/api/projects":
            self._json({"ok": True, "items": list_projects()})
            return

        if parsed.path == "/api/project":
            project_id = query.get("id", [""])[0]
            project = get_project(project_id)
            if not project:
                self._json({"ok": False, "error": "Проект не найден."}, HTTPStatus.NOT_FOUND)
            else:
                self._json({"ok": True, "project": project, "tasks": list_tasks(project_id=project_id), "context": build_context(project_id=project_id)})
            return

        if parsed.path == "/api/tasks":
            project_id = query.get("project_id", [None])[0]
            status = query.get("status", [None])[0]
            self._json({"ok": True, "items": list_tasks(project_id=project_id, status=status)})
            return

        if parsed.path == "/api/task":
            task_id = query.get("id", [""])[0]
            task = get_task(task_id)
            if not task:
                self._json({"ok": False, "error": "Задача не найдена."}, HTTPStatus.NOT_FOUND)
            else:
                self._json({"ok": True, "task": task, "context": build_context(project_id=task.get("project_id"), task_id=task_id)})
            return

        if parsed.path == "/api/context":
            project_id = query.get("project_id", [None])[0]
            task_id = query.get("task_id", [None])[0]
            self._json({"ok": True, **build_context(project_id=project_id, task_id=task_id)})
            return

        if parsed.path == "/api/brain/status":
            self._json({"ok": True, **brain_status()})
            return

        if parsed.path == "/api/brain/architecture":
            self._json({"ok": True, **architecture_state()})
            return

        if parsed.path == "/api/brain/overview":
            self._json({"ok": True, "brain": brain_status(), **overview_state()})
            return

        if parsed.path == "/api/brain/development":
            self._json({"ok": True, "items": list_proposals()})
            return

        if parsed.path == "/api/brain/models":
            self._json({
                "ok": True,
                "summary": model_registry_summary(),
                "items": list_brain_models(),
                "runtime": neural_runtime_status(),
                "evaluations": model_evaluation_reports(20),
            })
            return

        if parsed.path == "/api/brain/memory/semantic":
            self._json({"ok": True, **semantic_memory_status()})
            return

        if parsed.path == "/api/chat/sessions":
            self._json({"ok": True, "items": brain_list_sessions()})
            return

        if parsed.path == "/api/chat/session":
            session_id = query.get("id", [""])[0]
            self._json({"ok": True, "session": brain_get_session(session_id)})
            return

        if parsed.path == "/api/assistant/capabilities":
            self._json({"ok": True, **capability_manifest()})
            return

        if parsed.path == "/api/assistant/state":
            self._json({"ok": True, **state_snapshot()})
            return

        if parsed.path == "/api/assistant/audit":
            self._json({"ok": True, "items": audit_log()})
            return

        if parsed.path == "/api/account":
            self._json({"ok": True, "profile": get_profile(), "devices": list_devices(), "pairing": pairing_status(), "cloudru": cloudru_status()})
            return

        if parsed.path == "/api/cloudru/status":
            self._json({"ok": True, **cloudru_status()})
            return

        if parsed.path == "/api/cloudru/configs":
            self._json({"ok": True, "items": cloudru_training_configs()})
            return

        if parsed.path == "/api/cloudru/jobs":
            self._json({"ok": True, "items": cloudru_job_history()})
            return

        if parsed.path == "/api/training/datasets":
            self._json({"ok": True, "items": list_training_datasets()})
            return

        if parsed.path == "/api/update/check":
            try:
                self._json(check_update())
            except UpdateError as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return

        if parsed.path == "/api/update/progress":
            self._json({"ok": True, **update_progress()})
            return

        if parsed.path == "/api/update/history":
            self._json({"ok": True, "items": update_history()})
            return

        if parsed.path == "/api/mobile/update/check":
            try:
                self._json(mobile_update_status())
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
            file_content = candidate.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        mime, _ = mimetypes.guess_type(candidate.name)
        content_type = mime or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
            content_type += "; charset=utf-8"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(file_content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(file_content)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_json_body()

        try:
            if parsed.path == "/api/memory/add":
                item = add_memory(
                    str(payload.get("category", "")),
                    str(payload.get("text", "")),
                    payload.get("entity_type"),
                    payload.get("entity_id"),
                )
                self._json({"ok": True, "item": item, **get_memory(), "active_context": active_context()})
                return

            if parsed.path == "/api/memory/delete":
                self._json({"ok": True, "deleted": delete_memory(str(payload.get("id", ""))), **get_memory(), "active_context": active_context()})
                return

            if parsed.path == "/api/memory/category":
                result = set_category_enabled(str(payload.get("category", "")), bool(payload.get("enabled", False)))
                self._json({"ok": True, **result, **get_memory(), "active_context": active_context()})
                return

            if parsed.path == "/api/project/create":
                project = create_project(str(payload.get("name", "")), str(payload.get("description", "")))
                self._json({"ok": True, "project": project})
                return

            if parsed.path == "/api/project/update":
                project = update_project(str(payload.get("id", "")), payload.get("changes", {}))
                self._json({"ok": True, "project": project})
                return

            if parsed.path == "/api/project/delete":
                self._json({"ok": True, "deleted": delete_project(str(payload.get("id", "")))})
                return

            if parsed.path == "/api/task/create":
                task = create_task(
                    str(payload.get("title", "")),
                    payload.get("project_id"),
                    str(payload.get("description", "")),
                    str(payload.get("priority", "normal")),
                    payload.get("due_at"),
                )
                self._json({"ok": True, "task": task})
                return

            if parsed.path == "/api/task/update":
                task = update_task(str(payload.get("id", "")), payload.get("changes", {}))
                self._json({"ok": True, "task": task})
                return

            if parsed.path == "/api/task/delete":
                self._json({"ok": True, "deleted": delete_task(str(payload.get("id", "")))})
                return

            if parsed.path == "/api/brain/sleep":
                self._json({"ok": True, "result": consolidate_now()})
                return

            if parsed.path == "/api/brain/model/evaluate":
                report = evaluate_brain_model(
                    str(payload.get("model_id", "")),
                    context=build_context(
                        project_id=payload.get("project_id"),
                        task_id=payload.get("task_id"),
                        query=str(payload.get("query", "model evaluation")),
                    ),
                )
                self._json({"ok": True, "report": report})
                return

            if parsed.path == "/api/brain/development/propose":
                proposal = propose_development(
                    str(payload.get("title", "")),
                    str(payload.get("rationale", "")),
                    str(payload.get("target", "")),
                    str(payload.get("risk", "medium")),
                )
                self._json({"ok": True, "proposal": proposal})
                return

            if parsed.path == "/api/brain/development/transition":
                proposal = transition_development(
                    str(payload.get("id", "")),
                    str(payload.get("state", "")),
                    note=payload.get("note"),
                    approved=bool(payload.get("approved", False)),
                )
                self._json({"ok": True, "proposal": proposal})
                return

            if parsed.path == "/api/chat/session/create":
                self._json({"ok": True, "session": brain_create_session(str(payload.get("title", "")))})
                return

            if parsed.path == "/api/chat/session/rename":
                self._json({"ok": True, "session": brain_rename_session(str(payload.get("id", "")), str(payload.get("title", "")))})
                return

            if parsed.path == "/api/chat/session/delete":
                self._json({"ok": True, "deleted": brain_delete_session(str(payload.get("id", "")))})
                return

            if parsed.path == "/api/brain/think":
                result = brain_think(
                    str(payload.get("message", "")),
                    session_id=str(payload.get("session_id", "default")),
                    project_id=payload.get("project_id"),
                    task_id=payload.get("task_id"),
                    confirmed=bool(payload.get("confirmed", False)),
                )
                self._json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.CONFLICT)
                return

            if parsed.path == "/api/assistant/action":
                result = execute_action(
                    str(payload.get("action", "")),
                    payload.get("arguments", {}),
                    actor=str(payload.get("actor", "miyori")),
                    confirmed=bool(payload.get("confirmed", False)),
                )
                self._json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.CONFLICT)
                return

            if parsed.path == "/api/account/save":
                self._json({"ok": True, "profile": save_profile(payload)})
                return

            if parsed.path == "/api/cloudru/save":
                self._json({"ok": True, "cloudru": save_cloudru_credentials(payload)})
                return

            if parsed.path == "/api/cloudru/test":
                self._json({"ok": True, **cloudru_test_connection()})
                return

            if parsed.path == "/api/training/dataset/build":
                dataset = build_training_dataset(
                    name=str(payload.get("name", "miyori-learning")),
                    include_sessions=bool(payload.get("include_sessions", True)),
                )
                self._json({"ok": True, "dataset": dataset})
                return

            if parsed.path == "/api/cloudru/training/submit":
                job = cloudru_submit_training_job(payload)
                self._json({"ok": True, "job": job})
                return

            if parsed.path == "/api/account/pairing":
                self._json({"ok": True, **create_pairing()})
                return

            if parsed.path == "/api/account/device/revoke":
                device_id = str(payload.get("device_id", ""))
                self._json({"ok": True, "revoked": revoke_device(device_id), "devices": list_devices()})
                return

            if parsed.path == "/api/update/apply":
                self._json({"ok": True, **start_update()})
                return

            if parsed.path == "/api/mobile/update/download":
                self._json(download_mobile_client())
                return

        except KeyError as exc:
            self._json({"ok": False, "error": str(exc).strip("'")}, HTTPStatus.NOT_FOUND)
            return
        except PermissionError as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.FORBIDDEN)
            return
        except ValueError as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except CloudRuError as exc:
            log.warning("Cloud.ru action failed: %s", exc)
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return
        except UpdateError as exc:
            log.warning("Update action failed: %s", exc)
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return
        except Exception:
            log.exception("Unexpected API failure at %s", parsed.path)
            self._json({"ok": False, "error": "Внутренняя ошибка Miyori Core."}, HTTPStatus.INTERNAL_SERVER_ERROR)
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
    start_brain_scheduler()
    log.info("Miyori Brain sleep/consolidation scheduler started")

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        log.info("Shutdown requested")
    finally:
        stop_brain_scheduler()
        server.server_close()
        log.info("Core stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
