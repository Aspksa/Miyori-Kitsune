from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEARNING_FILE = ROOT / "data" / "brain" / "learning.json"

STAGES = ("observed", "confirmed", "retained", "applied", "reassessed")

def _read():
    try:
        data = json.loads(LEARNING_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []

def _write(rows):
    LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEARNING_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LEARNING_FILE)

def observe(subject: str, statement: str, source: str = "experience"):
    item = {
        "id": "learning_" + uuid.uuid4().hex[:12],
        "subject": str(subject),
        "statement": str(statement),
        "source": source,
        "stage": "observed",
        "confidence": 0.3,
        "evidence": [],
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    rows = _read()
    rows.append(item)
    _write(rows[-2000:])
    return item

def advance(item_id: str, evidence: str | None = None):
    rows = _read()
    target = next((x for x in rows if x.get("id") == item_id), None)
    if not target:
        raise KeyError("Learning item not found.")
    index = STAGES.index(target.get("stage", "observed"))
    if index < len(STAGES) - 1:
        target["stage"] = STAGES[index + 1]
    if evidence:
        target.setdefault("evidence", []).append(str(evidence))
    target["confidence"] = min(1.0, float(target.get("confidence", 0.3)) + 0.15)
    target["updated_at"] = int(time.time())
    _write(rows)
    return target

def list_learning(limit: int = 100):
    return list(reversed(_read()[-max(1, min(limit, 500)):]))
