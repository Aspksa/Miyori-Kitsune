from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMORY_FILE = ROOT / "data" / "memory.json"

CATEGORIES = {
    "projects": "Проекты",
    "work": "Работа",
    "tasks": "Задачи",
    "remember": "Запомнить",
    "preferences": "Предпочтения",
    "people": "Люди",
    "facts": "Важные факты",
}


def _default():
    return {"enabled": {key: True for key in CATEGORIES}, "items": []}


def _read():
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default()
    except (OSError, json.JSONDecodeError):
        return _default()

    enabled = _default()["enabled"]
    enabled.update({k: bool(v) for k, v in data.get("enabled", {}).items() if k in CATEGORIES})
    items = [item for item in data.get("items", []) if isinstance(item, dict) and item.get("category") in CATEGORIES]
    return {"enabled": enabled, "items": items}


def _write(data):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = MEMORY_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(MEMORY_FILE)


def get_memory():
    state = _read()
    return {
        "categories": [
            {
                "id": key,
                "label": label,
                "enabled": state["enabled"].get(key, True),
                "count": sum(1 for item in state["items"] if item.get("category") == key),
            }
            for key, label in CATEGORIES.items()
        ],
        "items": sorted(state["items"], key=lambda item: int(item.get("updated_at", 0)), reverse=True),
    }


def add_memory(category, text, entity_type=None, entity_id=None):
    if category not in CATEGORIES:
        raise ValueError("Неизвестная категория памяти.")
    text = str(text).strip()
    if not text:
        raise ValueError("Запись памяти пустая.")
    if len(text) > 2000:
        raise ValueError("Запись памяти слишком длинная.")

    entity_type = str(entity_type or "").strip() or None
    entity_id = str(entity_id or "").strip() or None
    if entity_type not in {None, "project", "task"}:
        raise ValueError("Память можно привязать только к проекту или задаче.")
    if bool(entity_type) != bool(entity_id):
        raise ValueError("Для связи памяти нужны entity_type и entity_id.")

    state = _read()
    now = int(time.time())
    item = {
        "id": uuid.uuid4().hex[:12],
        "category": category,
        "text": text,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "created_at": now,
        "updated_at": now,
    }
    state["items"].append(item)
    _write(state)
    return item


def delete_memory(item_id):
    state = _read()
    count = len(state["items"])
    state["items"] = [item for item in state["items"] if item.get("id") != item_id]
    changed = len(state["items"]) != count
    if changed:
        _write(state)
    return changed


def set_category_enabled(category, enabled):
    if category not in CATEGORIES:
        raise ValueError("Неизвестная категория памяти.")
    state = _read()
    state["enabled"][category] = bool(enabled)
    _write(state)
    return {"category": category, "enabled": state["enabled"][category]}


def active_context(project_id=None, task_id=None):
    state = _read()
    items = []
    for item in state["items"]:
        if not state["enabled"].get(item.get("category"), False):
            continue
        entity_type = item.get("entity_type")
        entity_id = item.get("entity_id")
        if not entity_type:
            items.append(item)
        elif entity_type == "project" and project_id and entity_id == project_id:
            items.append(item)
        elif entity_type == "task" and task_id and entity_id == task_id:
            items.append(item)

    return {
        "enabled_categories": [key for key, enabled in state["enabled"].items() if enabled],
        "items": items,
        "count": len(items),
        "scope": {"project_id": project_id, "task_id": task_id},
    }
