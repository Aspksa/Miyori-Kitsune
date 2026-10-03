from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFLECTION_FILE = ROOT / "data" / "brain" / "reflections.json"

def _read():
    try:
        data = json.loads(REFLECTION_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []

def _write(rows):
    REFLECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REFLECTION_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(REFLECTION_FILE)

def reflect(event: dict):
    outcome = event.get("outcome", "unknown")
    errors = event.get("errors", [])
    lessons = []
    if errors:
        lessons.append("Review failed assumptions and tool results before repeating this plan.")
    if outcome == "success":
        lessons.append("Keep successful action sequence as reusable evidence.")
    if not lessons:
        lessons.append("Insufficient evidence; retain as observation, not a stable rule.")
    item = {
        "id": "reflection_" + uuid.uuid4().hex[:12],
        "time": int(time.time()),
        "source": event,
        "lessons": lessons,
        "confidence": 0.6 if outcome == "success" else 0.4,
    }
    rows = _read()
    rows.append(item)
    _write(rows[-1000:])
    return item

def list_reflections(limit: int = 100):
    return list(reversed(_read()[-max(1, min(limit, 500)):]))
