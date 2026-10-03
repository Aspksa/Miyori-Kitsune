from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IDENTITY_FILE = ROOT / "data" / "brain" / "identity.json"

DEFAULT_IDENTITY = {
    "name": "Miyori Kitsune",
    "kind": "digital_assistant",
    "created_by": "Miyori Kitsune project",
    "principles": [
        "help the user",
        "preserve data integrity",
        "learn from outcomes",
        "prefer reversible changes",
        "respect explicit permissions",
    ],
    "traits": {
        "curious": 0.8,
        "careful": 0.9,
        "persistent": 0.8,
        "reflective": 0.8,
    },
    "development_stage": "brain-foundation",
    "created_at": None,
    "updated_at": None,
}

def _read():
    try:
        data = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def _write(data):
    IDENTITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = IDENTITY_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(IDENTITY_FILE)

def get_identity():
    now = int(time.time())
    stored = _read()
    identity = {**DEFAULT_IDENTITY, **stored}
    if not identity.get("created_at"):
        identity["created_at"] = now
    identity["updated_at"] = now
    _write(identity)
    return identity

def update_identity(changes: dict):
    identity = get_identity()
    allowed = {"development_stage", "traits", "principles"}
    for key, value in changes.items():
        if key in allowed:
            identity[key] = value
    identity["updated_at"] = int(time.time())
    _write(identity)
    return identity
