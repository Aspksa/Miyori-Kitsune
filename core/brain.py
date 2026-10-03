from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from assistant_gateway import build_context, capability_manifest, execute_action
from entities import get_project, list_projects, list_tasks

ROOT = Path(__file__).resolve().parent.parent
BRAIN_DIR = ROOT / "data" / "brain"
SESSIONS_DIR = BRAIN_DIR / "sessions"
BRAIN_LOG = BRAIN_DIR / "brain-events.json"

BRAIN_NAME = "Miyori Kitsune"
BRAIN_VERSION = "0.1.0"


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


def _event(kind: str, payload: dict) -> None:
    rows = _read_json(BRAIN_LOG, [])
    if not isinstance(rows, list):
        rows = []
    rows.append({"id": uuid.uuid4().hex[:12], "time": _now(), "kind": kind, "payload": payload})
    _write_json(BRAIN_LOG, rows[-2000:])


def _session_path(session_id: str) -> Path:
    safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")[:64]
    return SESSIONS_DIR / f"{safe or 'default'}.json"


def _append_session(session_id: str, role: str, content: str, meta: dict | None = None) -> None:
    path = _session_path(session_id)
    data = _read_json(path, {"id": session_id, "messages": []})
    if not isinstance(data, dict):
        data = {"id": session_id, "messages": []}
    messages = data.setdefault("messages", [])
    messages.append({
        "id": uuid.uuid4().hex[:12],
        "role": role,
        "content": content,
        "time": _now(),
        "meta": meta or {},
    })
    data["messages"] = messages[-200:]
    data["updated_at"] = _now()
    _write_json(path, data)


def status() -> dict:
    return {
        "name": BRAIN_NAME,
        "version": BRAIN_VERSION,
        "runtime": "miyori-cognitive-runtime",
        "model": "internal-rule-planner",
        "ready": True,
        "external_model": False,
        "capabilities": capability_manifest(),
    }


def _normalize(text: str) -> str:
    return " ".join(str(text).strip().split())


def _find_project_by_name(name: str) -> dict | None:
    wanted = _normalize(name).lower()
    if not wanted:
        return None
    projects = list_projects()
    exact = next((p for p in projects if str(p.get("name", "")).lower() == wanted), None)
    if exact:
        return exact
    return next((p for p in projects if wanted in str(p.get("name", "")).lower()), None)


def _extract_project_reference(text: str) -> dict | None:
    lower = text.lower()
    for project in list_projects():
        name = str(project.get("name", ""))
        if name and name.lower() in lower:
            return project
    match = re.search(r"(?:в проект(?:е|)\s+|для проекта\s+)([^,.!?]+)", text, re.I)
    if match:
        return _find_project_by_name(match.group(1))
    return None


def _plan(text: str, project_id: str | None = None) -> dict:
    clean = _normalize(text)
    lower = clean.lower()
    context = build_context(project_id=project_id)

    match = re.match(r"^(?:создай|создать|добавь)\s+проект\s+(.+)$", clean, re.I)
    if match:
        name = match.group(1).strip(" .")
        return {"intent": "project.create", "actions": [{"action": "project.create", "arguments": {"name": name}}], "context": context}

    task_match = re.match(r"^(?:создай|создать|добавь)\s+(?:новую\s+)?задач[ау]\s+(.+)$", clean, re.I)
    if task_match:
        remainder = task_match.group(1).strip()
        linked = _extract_project_reference(clean)
        title = remainder
        if linked:
            patterns = [
                r"\s+в проект(?:е|)\s+" + re.escape(str(linked.get("name", ""))) + r".*$",
                r"\s+для проекта\s+" + re.escape(str(linked.get("name", ""))) + r".*$",
            ]
            for pattern in patterns:
                title = re.sub(pattern, "", title, flags=re.I).strip()
        return {
            "intent": "task.create",
            "actions": [{
                "action": "task.create",
                "arguments": {"title": title or "Новая задача", "project_id": linked.get("id") if linked else project_id},
            }],
            "context": context,
        }

    remember_match = re.match(r"^запомни(?:,|\s+что)?\s+(.+)$", clean, re.I)
    if remember_match:
        return {
            "intent": "memory.add",
            "actions": [{
                "action": "memory.add",
                "arguments": {
                    "category": "remember",
                    "text": remember_match.group(1).strip(),
                    "entity_type": "project" if project_id else None,
                    "entity_id": project_id,
                },
            }],
            "context": context,
        }

    if any(x in lower for x in ["какие задачи", "мои задачи", "что по задачам", "покажи задачи"]):
        project = get_project(project_id) if project_id else _extract_project_reference(clean)
        tasks = list_tasks(project_id=project.get("id")) if project else list_tasks()
        return {"intent": "task.list", "actions": [], "context": build_context(project_id=project.get("id") if project else None), "result_data": {"tasks": tasks}}

    if any(x in lower for x in ["что по проекту", "расскажи про проект", "статус проекта"]):
        project = get_project(project_id) if project_id else _extract_project_reference(clean)
        return {"intent": "project.inspect", "actions": [], "context": build_context(project_id=project.get("id") if project else None), "result_data": {"project": project}}

    return {"intent": "conversation", "actions": [], "context": context}


def _render(plan: dict, action_results: list[dict]) -> str:
    intent = plan.get("intent")
    if intent == "project.create" and action_results:
        project = action_results[-1].get("result", {})
        return f"Создала проект «{project.get('name', 'Новый проект')}»."
    if intent == "task.create" and action_results:
        task = action_results[-1].get("result", {})
        return f"Создала задачу «{task.get('title', 'Новая задача')}»."
    if intent == "memory.add" and action_results:
        return "Сохранила это в память Miyori."
    if intent == "task.list":
        tasks = plan.get("result_data", {}).get("tasks", [])
        active = [task for task in tasks if task.get("status") != "done"]
        if not active:
            return "Активных задач сейчас нет."
        names = ", ".join(str(task.get("title", "Задача")) for task in active[:8])
        suffix = f" и ещё {len(active)-8}" if len(active) > 8 else ""
        return f"Активные задачи: {names}{suffix}."
    if intent == "project.inspect":
        project = plan.get("result_data", {}).get("project")
        if not project:
            return "Не нашла такой проект."
        context = plan.get("context", {})
        return f"Проект «{project.get('name')}»: статус {project.get('status')}, задач {len(context.get('tasks', []))}, записей памяти {context.get('memory', {}).get('count', 0)}."
    return "Я получила запрос и собрала доступный контекст. Полноценный генеративный ответ появится после подключения обучаемого runtime Miyori; инструменты, память и планировщик уже готовы."


def think(message: str, session_id: str = "default", project_id: str | None = None, task_id: str | None = None, confirmed: bool = False) -> dict:
    message = _normalize(message)
    if not message:
        raise ValueError("Пустой запрос.")

    _append_session(session_id, "user", message, {"project_id": project_id, "task_id": task_id})
    plan = _plan(message, project_id=project_id)
    action_results = []

    for step in plan.get("actions", []):
        result = execute_action(
            step["action"],
            step.get("arguments", {}),
            actor="miyori-brain",
            confirmed=confirmed,
        )
        action_results.append(result)
        if result.get("requires_confirmation"):
            response = "Это действие требует подтверждения."
            _append_session(session_id, "assistant", response, {"plan": plan, "actions": action_results})
            _event("requires_confirmation", {"message": message, "plan": plan, "actions": action_results})
            return {
                "ok": False,
                "requires_confirmation": True,
                "reply": response,
                "plan": plan,
                "actions": action_results,
                "brain": status(),
            }

    response = _render(plan, action_results)
    context = build_context(project_id=project_id, task_id=task_id)
    _append_session(session_id, "assistant", response, {"intent": plan.get("intent"), "actions": action_results})
    _event("thought", {"message": message, "intent": plan.get("intent"), "actions": action_results})

    return {
        "ok": True,
        "reply": response,
        "intent": plan.get("intent"),
        "actions": action_results,
        "context": context,
        "brain": status(),
    }
