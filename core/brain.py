from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from assistant_gateway import build_context, capability_manifest, execute_action
from brain_runtime import InternalPlannerRuntime
from cognitive_loop import conclude, perceive
from embodiment import status as embodiment_status
from entities import get_project, list_projects, list_tasks
from identity import get_identity
from learning import observe
from memory import memory_engine_status
from model_registry import summary as model_registry_summary
from neural_runtime import active_runtime, runtime_status
from skills import registry as skill_registry
from student_gateway import status as student_status
from teacher_gateway import review_if_enabled as teacher_review_if_enabled, status as teacher_status
from world_model import snapshot as world_snapshot

ROOT = Path(__file__).resolve().parent.parent
BRAIN_DIR = ROOT / "data" / "brain"
SESSIONS_DIR = BRAIN_DIR / "sessions"
BRAIN_LOG = BRAIN_DIR / "brain-events.json"

BRAIN_NAME = "Miyori Kitsune"
BRAIN_VERSION = "0.5.0"
FALLBACK_RUNTIME = InternalPlannerRuntime()


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


def _session_title(messages: list[dict]) -> str:
    for message in messages:
        if message.get("role") == "user":
            text = " ".join(str(message.get("content", "")).split())
            if text:
                return text[:56] + ("…" if len(text) > 56 else "")
    return "Новый диалог"


def list_sessions(limit: int = 50) -> list[dict]:
    if not SESSIONS_DIR.exists():
        return []
    rows = []
    for path in SESSIONS_DIR.glob("*.json"):
        data = _read_json(path, {})
        if not isinstance(data, dict):
            continue
        messages = data.get("messages", [])
        rows.append({
            "id": str(data.get("id") or path.stem),
            "title": str(data.get("title") or _session_title(messages)),
            "updated_at": int(data.get("updated_at", 0) or 0),
            "created_at": int(data.get("created_at", data.get("updated_at", 0)) or 0),
            "message_count": len(messages),
            "preview": str(messages[-1].get("content", ""))[:120] if messages else "",
        })
    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return rows[:max(1, min(limit, 200))]


def get_session(session_id: str) -> dict:
    path = _session_path(session_id)
    data = _read_json(path, None)
    if not isinstance(data, dict):
        raise KeyError("Диалог не найден.")
    messages = data.get("messages", [])
    return {
        "id": str(data.get("id") or session_id),
        "title": str(data.get("title") or _session_title(messages)),
        "created_at": int(data.get("created_at", 0) or 0),
        "updated_at": int(data.get("updated_at", 0) or 0),
        "messages": messages[-200:],
    }


def create_session(title: str = "") -> dict:
    session_id = "session_" + uuid.uuid4().hex[:12]
    now = _now()
    data = {
        "id": session_id,
        "title": str(title).strip()[:80] or "Новый диалог",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    _write_json(_session_path(session_id), data)
    return get_session(session_id)


def rename_session(session_id: str, title: str) -> dict:
    title = " ".join(str(title).split())[:80]
    if not title:
        raise ValueError("Название диалога пустое.")
    path = _session_path(session_id)
    data = _read_json(path, None)
    if not isinstance(data, dict):
        raise KeyError("Диалог не найден.")
    data["title"] = title
    data["updated_at"] = _now()
    _write_json(path, data)
    return get_session(session_id)


def delete_session(session_id: str) -> bool:
    path = _session_path(session_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def _append_session(session_id: str, role: str, content: str, meta: dict | None = None) -> None:
    path = _session_path(session_id)
    data = _read_json(path, {"id": session_id, "messages": []})
    if not isinstance(data, dict):
        data = {"id": session_id, "messages": []}
    if not data.get("created_at"):
        data["created_at"] = _now()
    messages = data.setdefault("messages", [])
    messages.append({
        "id": uuid.uuid4().hex[:12],
        "role": role,
        "content": content,
        "time": _now(),
        "meta": meta or {},
    })
    data["messages"] = messages[-200:]
    if not data.get("title") or data.get("title") == "Новый диалог":
        data["title"] = _session_title(data["messages"])
    data["updated_at"] = _now()
    _write_json(path, data)


def _recent_dialogue(session_id: str, limit: int = 12) -> list[dict]:
    path = _session_path(session_id)
    data = _read_json(path, {})
    messages = data.get("messages", []) if isinstance(data, dict) else []
    rows = []
    for item in messages[-max(1, min(int(limit), 30)):]:
        role = str(item.get("role", ""))
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            rows.append({"role": role, "content": content})
    return rows


def status() -> dict:
    models = model_registry_summary()
    body = embodiment_status()
    runtime = runtime_status()
    active_model = models.get("active", {})
    return {
        "name": BRAIN_NAME,
        "version": BRAIN_VERSION,
        "runtime": "miyori-cognitive-runtime",
        "model_runtime": runtime.get("name"),
        "model_runtime_version": runtime.get("version"),
        "model_runtime_available": runtime.get("available"),
        "runtime_state": runtime,
        "ready": True,
        "external_model": active_model.get("runtime") not in {None, "internal"},
        "active_model": active_model,
        "models": models,
        "memory_engine": memory_engine_status(),
        "student": student_status(),
        "teacher": teacher_status(),
        "embodiment": body,
        "identity": get_identity(),
        "skills": skill_registry(),
        "world_model": {
            "nodes": len(world_snapshot().get("nodes", {})),
            "edges": len(world_snapshot().get("edges", [])),
        },
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
    context = build_context(project_id=project_id, query=clean)

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
    perception = perceive(message, project_id=project_id, task_id=task_id)
    base_context = perception["context"]
    base_context["conversation_history"] = _recent_dialogue(session_id)
    runtime = active_runtime()
    if not runtime.available():
        runtime = FALLBACK_RUNTIME
    runtime_output = runtime.infer(message, base_context, perception["capabilities"])
    if (
        runtime is not FALLBACK_RUNTIME
        and not str(runtime_output.text or "").strip()
        and (runtime_output.metadata or {}).get("available") is False
    ):
        failed_metadata = dict(runtime_output.metadata or {})
        runtime = FALLBACK_RUNTIME
        runtime_output = runtime.infer(message, base_context, perception["capabilities"])
        runtime_output.metadata = {
            **(runtime_output.metadata or {}),
            "fallback_from": failed_metadata.get("runtime"),
            "fallback_error": failed_metadata.get("error"),
        }
    plan = _plan(message, project_id=project_id)
    plan["runtime"] = runtime_output.metadata or {}
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
            reflection = conclude(perception, plan.get("intent", "unknown"), plan.get("actions", []), "requires_confirmation")
            _append_session(session_id, "assistant", response, {"plan": plan, "actions": action_results, "reflection": reflection})
            _event("requires_confirmation", {"message": message, "plan": plan, "actions": action_results})
            return {
                "ok": False,
                "requires_confirmation": True,
                "reply": response,
                "plan": plan,
                "actions": action_results,
                "brain": status(),
            }

    response = (
        str(runtime_output.text).strip()
        if plan.get("intent") == "conversation" and str(runtime_output.text or "").strip()
        else _render(plan, action_results)
    )
    context = build_context(project_id=project_id, task_id=task_id, query=message)
    reflection = conclude(perception, plan.get("intent", "unknown"), plan.get("actions", []), "success")
    teacher_feedback = teacher_review_if_enabled(
        message,
        response,
        context=context,
        session_id=session_id,
    )
    learning_item = None
    if plan.get("intent") not in {"conversation", "task.list", "project.inspect"}:
        learning_item = observe(plan.get("intent", "unknown"), "Action cycle completed successfully.", source="brain-cycle")
    _append_session(session_id, "assistant", response, {
        "intent": plan.get("intent"),
        "actions": action_results,
        "reflection": reflection,
        "learning": learning_item,
        "teacher_feedback_id": teacher_feedback.get("id") if isinstance(teacher_feedback, dict) else None,
    })
    _event("thought", {"message": message, "intent": plan.get("intent"), "actions": action_results})

    return {
        "ok": True,
        "reply": response,
        "intent": plan.get("intent"),
        "actions": action_results,
        "context": context,
        "reflection": reflection,
        "learning": learning_item,
        "teacher_feedback": teacher_feedback,
        "pipeline": {
            "student_runtime": (runtime_output.metadata or {}).get("runtime", getattr(runtime, "name", "unknown")),
            "memory_retrieval": context.get("memory", {}).get("retrieval"),
            "student_active": (runtime_output.metadata or {}).get("student", False),
            "fallback_from": (runtime_output.metadata or {}).get("fallback_from"),
            "fallback_error": (runtime_output.metadata or {}).get("fallback_error"),
            "teacher_reviewed": bool(isinstance(teacher_feedback, dict) and teacher_feedback.get("id")),
            "teacher_error": teacher_feedback.get("error") if isinstance(teacher_feedback, dict) else None,
        },
        "brain": status(),
    }
