from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEV_DIR = ROOT / "data" / "brain" / "self-development"
PROPOSALS_FILE = DEV_DIR / "proposals.json"

ALLOWED_STATES = {"proposed", "sandboxed", "tested", "approved", "rejected", "applied", "rolled_back"}

def _read():
    try:
        data = json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []

def _write(rows):
    PROPOSALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROPOSALS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROPOSALS_FILE)

def propose(title: str, rationale: str, target: str, risk: str = "medium"):
    item = {
        "id": "proposal_" + uuid.uuid4().hex[:12],
        "title": str(title)[:200],
        "rationale": str(rationale)[:4000],
        "target": str(target)[:300],
        "risk": risk if risk in {"low", "medium", "high"} else "medium",
        "state": "proposed",
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
        "artifacts": [],
        "tests": [],
    }
    rows = _read()
    rows.append(item)
    _write(rows[-1000:])
    return item

def transition(proposal_id: str, state: str, note: str | None = None):
    if state not in ALLOWED_STATES:
        raise ValueError("Invalid self-development state.")
    rows = _read()
    item = next((x for x in rows if x.get("id") == proposal_id), None)
    if not item:
        raise KeyError("Proposal not found.")
    item["state"] = state
    item["updated_at"] = int(time.time())
    if note:
        item.setdefault("notes", []).append({"time": int(time.time()), "text": str(note)})
    _write(rows)
    return item

def list_proposals(limit: int = 100):
    return list(reversed(_read()[-max(1, min(limit, 500)):]))
