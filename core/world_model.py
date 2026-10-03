from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORLD_FILE = ROOT / "data" / "brain" / "world-model.json"

def _read():
    try:
        data = json.loads(WORLD_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"nodes": {}, "edges": [], "updated_at": 0}

def _write(data):
    WORLD_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = WORLD_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(WORLD_FILE)

def upsert_node(node_type: str, external_id: str, label: str, attributes: dict | None = None):
    state = _read()
    key = f"{node_type}:{external_id}"
    node = state["nodes"].get(key, {
        "id": "node_" + uuid.uuid4().hex[:12],
        "type": node_type,
        "external_id": external_id,
        "created_at": int(time.time()),
    })
    node["label"] = str(label)
    node["attributes"] = attributes or {}
    node["updated_at"] = int(time.time())
    state["nodes"][key] = node
    state["updated_at"] = int(time.time())
    _write(state)
    return node

def relate(source_type: str, source_id: str, relation: str, target_type: str, target_id: str):
    state = _read()
    edge_key = (source_type, source_id, relation, target_type, target_id)
    for edge in state["edges"]:
        current = (edge["source_type"], edge["source_id"], edge["relation"], edge["target_type"], edge["target_id"])
        if current == edge_key:
            edge["updated_at"] = int(time.time())
            _write(state)
            return edge
    edge = {
        "id": "edge_" + uuid.uuid4().hex[:12],
        "source_type": source_type,
        "source_id": source_id,
        "relation": relation,
        "target_type": target_type,
        "target_id": target_id,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    state["edges"].append(edge)
    state["updated_at"] = int(time.time())
    _write(state)
    return edge

def snapshot():
    return _read()

def sync_from_context(context: dict):
    project = context.get("project")
    if project:
        upsert_node("project", project["id"], project.get("name", project["id"]), {"status": project.get("status")})
    for task in context.get("tasks", []):
        upsert_node("task", task["id"], task.get("title", task["id"]), {"status": task.get("status"), "priority": task.get("priority")})
        if task.get("project_id"):
            relate("project", task["project_id"], "contains", "task", task["id"])
    for item in context.get("memory", {}).get("items", []):
        upsert_node("memory", item["id"], item.get("text", "")[:120], {"category": item.get("category")})
        if item.get("entity_type") and item.get("entity_id"):
            relate(item["entity_type"], item["entity_id"], "has_memory", "memory", item["id"])
    return snapshot()
