from __future__ import annotations

import time
import uuid

from assistant_gateway import build_context, capability_manifest
from reflection import reflect
from skills import record_use
from world_model import sync_from_context

def perceive(message: str, project_id=None, task_id=None):
    context = build_context(project_id=project_id, task_id=task_id)
    sync_from_context(context)
    return {
        "id": "perception_" + uuid.uuid4().hex[:12],
        "time": int(time.time()),
        "message": message,
        "context": context,
        "capabilities": capability_manifest(),
    }

def conclude(perception: dict, intent: str, actions: list[dict], outcome: str, errors: list[str] | None = None):
    for action in actions:
        skill = {
            "project.": "projects.manage",
            "task.": "tasks.manage",
            "memory.": "memory.manage",
        }
        action_name = action.get("action", "")
        skill_id = next((value for prefix, value in skill.items() if action_name.startswith(prefix)), "context.resolve")
        record_use(skill_id, success=outcome == "success")
    return reflect({
        "perception_id": perception.get("id"),
        "intent": intent,
        "actions": actions,
        "outcome": outcome,
        "errors": errors or [],
    })
