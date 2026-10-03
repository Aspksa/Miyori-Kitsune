from __future__ import annotations

import json
import time
from pathlib import Path

from embeddings import cosine_similarity, get_provider, status as embedding_status

ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE = ROOT / "data" / "brain" / "memory-vectors.json"


def _read() -> dict:
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("schema_version", 1)
            data.setdefault("items", {})
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"schema_version": 1, "provider": None, "items": {}, "updated_at": 0}


def _write(data: dict) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(INDEX_FILE)


def sync(items: list[dict]) -> dict:
    provider = get_provider()
    provider_key = f"{provider.name}:{provider.version}"
    state = _read()
    changed = state.get("provider") != provider_key
    if changed:
        state = {"schema_version": 1, "provider": provider_key, "items": {}, "updated_at": 0}

    source_ids = set()
    indexed = state.setdefault("items", {})
    encoded = 0
    for item in items:
        item_id = str(item.get("id", "")).strip()
        text = str(item.get("text", "")).strip()
        if not item_id or not text:
            continue
        source_ids.add(item_id)
        updated_at = int(item.get("updated_at", 0) or 0)
        current = indexed.get(item_id)
        if current and int(current.get("updated_at", -1)) == updated_at:
            continue
        indexed[item_id] = {
            "updated_at": updated_at,
            "vector": provider.encode(text),
        }
        encoded += 1
        changed = True

    stale = [item_id for item_id in indexed if item_id not in source_ids]
    for item_id in stale:
        indexed.pop(item_id, None)
        changed = True

    if changed:
        state["provider"] = provider_key
        state["updated_at"] = int(time.time())
        _write(state)

    return {
        "provider": provider_key,
        "items": len(indexed),
        "encoded": encoded,
        "removed": len(stale),
        "updated_at": int(state.get("updated_at", 0)),
    }


def search(query: str, items: list[dict], limit: int = 50) -> list[dict]:
    query = str(query).strip()
    if not query:
        return []
    sync(items)
    provider = get_provider()
    state = _read()
    query_vector = provider.encode(query)
    by_id = {str(item.get("id")): item for item in items}
    rows = []
    for item_id, stored in state.get("items", {}).items():
        source = by_id.get(item_id)
        if source is None:
            continue
        score = cosine_similarity(query_vector, stored.get("vector", []))
        rows.append({"id": item_id, "semantic_score": round(float(score), 6)})
    rows.sort(key=lambda row: row["semantic_score"], reverse=True)
    return rows[:max(1, min(int(limit), 200))]


def status() -> dict:
    state = _read()
    return {
        "index_items": len(state.get("items", {})),
        "index_provider": state.get("provider"),
        "updated_at": int(state.get("updated_at", 0)),
        "embeddings": embedding_status(),
    }
