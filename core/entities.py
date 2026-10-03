from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROJECTS_DIR = DATA_DIR / "projects"
TASKS_DIR = DATA_DIR / "tasks"
AUDIT_FILE = DATA_DIR / "assistant-audit.json"

PROJECT_STATUSES = {"active", "paused", "completed", "archived"}
TASK_STATUSES = {"todo", "in_progress", "blocked", "done", "archived"}
TASK_PRIORITIES = {"low", "normal", "high", "critical"}


def _now() -> int:
    return int(time.time())


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _safe_id(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isalnum() or ch in "-_")[:64]


def _entity_path(directory: Path, entity_id: str) -> Path:
    safe = _safe_id(entity_id)
    if not safe:
        raise ValueError("Некорректный идентификатор.")
    return directory / f"{safe}.json"


def _list(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    result = []
    for path in directory.glob("*.json"):
        item = _read_json(path, None)
        if isinstance(item, dict):
            result.append(item)
    return sorted(result, key=lambda x: int(x.get("updated_at", 0)), reverse=True)


def list_projects() -> list[dict]:
    return _list(PROJECTS_DIR)


def get_project(project_id: str) -> dict | None:
    data = _read_json(_entity_path(PROJECTS_DIR, project_id), None)
    return data if isinstance(data, dict) else None


def create_project(name: str, description: str = "") -> dict:
    name = str(name).strip()
    if not name:
        raise ValueError("Название проекта обязательно.")
    now = _now()
    project = {
        "id": "project_" + uuid.uuid4().hex[:12],
        "name": name[:120],
        "description": str(description).strip()[:4000],
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "metadata": {},
    }
    _write_json(_entity_path(PROJECTS_DIR, project["id"]), project)
    return project


def update_project(project_id: str, changes: dict) -> dict:
    project = get_project(project_id)
    if not project:
        raise KeyError("Проект не найден.")
    if "name" in changes:
        name = str(changes["name"]).strip()
        if name:
            project["name"] = name[:120]
    if "description" in changes:
        project["description"] = str(changes["description"]).strip()[:4000]
    if "status" in changes and str(changes["status"]) in PROJECT_STATUSES:
        project["status"] = str(changes["status"])
    project["updated_at"] = _now()
    _write_json(_entity_path(PROJECTS_DIR, project_id), project)
    return project


def delete_project(project_id: str) -> bool:
    path = _entity_path(PROJECTS_DIR, project_id)
    if not path.exists():
        return False
    path.unlink()
    for task in list_tasks(project_id=project_id):
        update_task(task["id"], {"project_id": None})
    return True


def list_tasks(project_id: str | None = None, status: str | None = None) -> list[dict]:
    items = _list(TASKS_DIR)
    if project_id:
        items = [x for x in items if x.get("project_id") == project_id]
    if status:
        items = [x for x in items if x.get("status") == status]
    return items


def get_task(task_id: str) -> dict | None:
    data = _read_json(_entity_path(TASKS_DIR, task_id), None)
    return data if isinstance(data, dict) else None


def create_task(title: str, project_id: str | None = None, description: str = "", priority: str = "normal", due_at=None) -> dict:
    title = str(title).strip()
    if not title:
        raise ValueError("Название задачи обязательно.")
    if project_id and not get_project(project_id):
        raise ValueError("Указанный проект не найден.")
    if priority not in TASK_PRIORITIES:
        priority = "normal"
    now = _now()
    task = {
        "id": "task_" + uuid.uuid4().hex[:12],
        "title": title[:160],
        "description": str(description).strip()[:4000],
        "project_id": project_id or None,
        "status": "todo",
        "priority": priority,
        "due_at": due_at,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    _write_json(_entity_path(TASKS_DIR, task["id"]), task)
    return task


def update_task(task_id: str, changes: dict) -> dict:
    task = get_task(task_id)
    if not task:
        raise KeyError("Задача не найдена.")
    if "title" in changes:
        title = str(changes["title"]).strip()
        if title:
            task["title"] = title[:160]
    if "description" in changes:
        task["description"] = str(changes["description"]).strip()[:4000]
    if "status" in changes and str(changes["status"]) in TASK_STATUSES:
        task["status"] = str(changes["status"])
        task["completed_at"] = _now() if task["status"] == "done" else None
    if "priority" in changes and str(changes["priority"]) in TASK_PRIORITIES:
        task["priority"] = str(changes["priority"])
    if "project_id" in changes:
        project_id = changes["project_id"]
        if project_id and not get_project(str(project_id)):
            raise ValueError("Указанный проект не найден.")
        task["project_id"] = project_id or None
    if "due_at" in changes:
        task["due_at"] = changes["due_at"]
    task["updated_at"] = _now()
    _write_json(_entity_path(TASKS_DIR, task_id), task)
    return task


def delete_task(task_id: str) -> bool:
    path = _entity_path(TASKS_DIR, task_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def audit(actor: str, action: str, target_type: str, target_id: str | None, payload: dict | None = None, result: str = "success") -> dict:
    rows = _read_json(AUDIT_FILE, [])
    if not isinstance(rows, list):
        rows = []
    event = {
        "id": "audit_" + uuid.uuid4().hex[:12],
        "time": _now(),
        "actor": actor,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "payload": payload or {},
        "result": result,
    }
    rows.append(event)
    _write_json(AUDIT_FILE, rows[-1000:])
    return event


def audit_log(limit: int = 100) -> list[dict]:
    rows = _read_json(AUDIT_FILE, [])
    if not isinstance(rows, list):
        return []
    return list(reversed(rows[-max(1, min(limit, 500)):]))
