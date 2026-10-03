from __future__ import annotations

from embodiment import perception_manifest
from entities import (
    audit,
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
from memory import active_context, add_memory, get_memory

SAFE_ACTIONS = {
    "project.create",
    "project.update",
    "project.delete",
    "task.create",
    "task.update",
    "task.delete",
    "memory.add",
}

DESTRUCTIVE_ACTIONS = {"project.delete", "task.delete"}


def capability_manifest() -> dict:
    return {
        "version": "2",
        "actions": sorted(SAFE_ACTIONS),
        "destructive_actions": sorted(DESTRUCTIVE_ACTIONS),
        "embodiment": perception_manifest(),
        "policy": {
            "direct_file_access": False,
            "audit_required": True,
            "confirmation_recommended_for_destructive": True,
            "hardware_access_requires_adapter": True,
            "actuation_requires_gateway": True,
        },
    }


def build_context(project_id: str | None = None, task_id: str | None = None, query: str | None = None) -> dict:
    projects = list_projects()
    tasks = list_tasks(project_id=project_id) if project_id else list_tasks()
    selected_project = get_project(project_id) if project_id else None
    selected_task = get_task(task_id) if task_id else None
    memory = active_context(project_id=project_id, task_id=task_id, query=query)

    return {
        "project": selected_project,
        "task": selected_task,
        "projects": projects[:50],
        "tasks": tasks[:100],
        "memory": memory,
        "summary": {
            "projects": len(projects),
            "tasks": len(tasks),
            "active_memory_items": memory.get("count", 0),
            "memory_retrieval": memory.get("retrieval", "recent"),
        },
    }


def execute_action(action: str, arguments: dict | None = None, actor: str = "miyori", confirmed: bool = False) -> dict:
    arguments = arguments or {}
    if action not in SAFE_ACTIONS:
        raise ValueError("Действие не разрешено Action Gateway.")
    if action in DESTRUCTIVE_ACTIONS and not confirmed:
        return {"ok": False, "requires_confirmation": True, "action": action, "arguments": arguments}

    target_type = action.split(".", 1)[0]
    target_id = None
    try:
        if action == "project.create":
            result = create_project(arguments.get("name", ""), arguments.get("description", ""))
            target_id = result["id"]
        elif action == "project.update":
            target_id = str(arguments.get("id", ""))
            result = update_project(target_id, arguments.get("changes", {}))
        elif action == "project.delete":
            target_id = str(arguments.get("id", ""))
            result = {"deleted": delete_project(target_id)}
        elif action == "task.create":
            result = create_task(arguments.get("title", ""), arguments.get("project_id"), arguments.get("description", ""), arguments.get("priority", "normal"), arguments.get("due_at"))
            target_id = result["id"]
        elif action == "task.update":
            target_id = str(arguments.get("id", ""))
            result = update_task(target_id, arguments.get("changes", {}))
        elif action == "task.delete":
            target_id = str(arguments.get("id", ""))
            result = {"deleted": delete_task(target_id)}
        elif action == "memory.add":
            result = add_memory(arguments.get("category", "remember"), arguments.get("text", ""), arguments.get("entity_type"), arguments.get("entity_id"), importance=arguments.get("importance", 0.5), confidence=arguments.get("confidence", 0.7), source=arguments.get("source", actor))
            target_id = result["id"]
        else:
            raise ValueError("Неизвестное действие.")
        audit(actor, action, target_type, target_id, arguments, "success")
        return {"ok": True, "action": action, "result": result}
    except Exception:
        audit(actor, action, target_type, target_id, arguments, "failed")
        raise


def state_snapshot() -> dict:
    return {"projects": list_projects(), "tasks": list_tasks(), "memory": get_memory(), "capabilities": capability_manifest()}
