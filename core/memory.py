from __future__ import annotations

import json
import math
import re
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

_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]{2,}", re.UNICODE)


def _default():
    return {"enabled": {key: True for key in CATEGORIES}, "items": []}


def _normalize_item(item: dict) -> dict:
    row = dict(item)
    row["importance"] = max(0.0, min(1.0, float(row.get("importance", 0.5) or 0.5)))
    row["confidence"] = max(0.0, min(1.0, float(row.get("confidence", 0.7) or 0.7)))
    row["source"] = str(row.get("source") or "user")
    row["access_count"] = max(0, int(row.get("access_count", 0) or 0))
    row["last_accessed_at"] = int(row.get("last_accessed_at", 0) or 0)
    return row


def _read():
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default()
    except (OSError, json.JSONDecodeError):
        return _default()

    enabled = _default()["enabled"]
    enabled.update({k: bool(v) for k, v in data.get("enabled", {}).items() if k in CATEGORIES})
    items = [
        _normalize_item(item)
        for item in data.get("items", [])
        if isinstance(item, dict) and item.get("category") in CATEGORIES
    ]
    return {"enabled": enabled, "items": items}


def _write(data):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = MEMORY_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(MEMORY_FILE)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text))}


def _scope_matches(item: dict, project_id=None, task_id=None) -> bool:
    entity_type = item.get("entity_type")
    entity_id = item.get("entity_id")
    if not entity_type:
        return True
    if entity_type == "project":
        return bool(project_id and entity_id == project_id)
    if entity_type == "task":
        return bool(task_id and entity_id == task_id)
    return False


def _relevance_score(item: dict, query: str, now: int) -> float:
    query_tokens = _tokens(query)
    text_tokens = _tokens(item.get("text", ""))
    lexical = 0.0
    if query_tokens and text_tokens:
        lexical = len(query_tokens & text_tokens) / max(1, len(query_tokens))
        union = len(query_tokens | text_tokens)
        if union:
            lexical = max(lexical, len(query_tokens & text_tokens) / union)

    age_seconds = max(0, now - int(item.get("updated_at", 0) or 0))
    recency = math.exp(-age_seconds / (60 * 60 * 24 * 90)) if age_seconds else 1.0
    importance = float(item.get("importance", 0.5))
    confidence = float(item.get("confidence", 0.7))
    return round((lexical * 0.58) + (importance * 0.18) + (confidence * 0.14) + (recency * 0.10), 6)


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


def add_memory(category, text, entity_type=None, entity_id=None, importance: float = 0.5, confidence: float = 0.7, source: str = "user"):
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
        "importance": max(0.0, min(1.0, float(importance))),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "source": str(source or "user")[:120],
        "access_count": 0,
        "last_accessed_at": 0,
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


def retrieve_relevant(query: str, project_id=None, task_id=None, limit: int = 24):
    state = _read()
    now = int(time.time())
    rows = []
    for item in state["items"]:
        if not state["enabled"].get(item.get("category"), False):
            continue
        if not _scope_matches(item, project_id=project_id, task_id=task_id):
            continue
        row = dict(item)
        row["relevance"] = _relevance_score(item, query, now)
        rows.append(row)

    rows.sort(
        key=lambda item: (
            float(item.get("relevance", 0)),
            float(item.get("importance", 0)),
            int(item.get("updated_at", 0)),
        ),
        reverse=True,
    )
    return rows[:max(1, min(int(limit), 100))]


def active_context(project_id=None, task_id=None, query: str | None = None, limit: int = 50):
    state = _read()
    if query and str(query).strip():
        items = retrieve_relevant(str(query), project_id=project_id, task_id=task_id, limit=limit)
        retrieval = "relevance"
    else:
        items = [
            item for item in state["items"]
            if state["enabled"].get(item.get("category"), False)
            and _scope_matches(item, project_id=project_id, task_id=task_id)
        ]
        items.sort(key=lambda item: int(item.get("updated_at", 0)), reverse=True)
        items = items[:max(1, min(int(limit), 100))]
        retrieval = "recent"

    return {
        "enabled_categories": [key for key, enabled in state["enabled"].items() if enabled],
        "items": items,
        "count": len(items),
        "retrieval": retrieval,
        "query": str(query or ""),
        "scope": {"project_id": project_id, "task_id": task_id},
    }
