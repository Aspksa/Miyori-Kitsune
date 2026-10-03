from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from safety_kernel import allow_self_development_transition, classify_change

ROOT = Path(__file__).resolve().parent.parent
DEV_DIR = ROOT / "data" / "brain" / "self-development"
PROPOSALS_FILE = DEV_DIR / "proposals.json"

ALLOWED_STATES = {"proposed", "sandboxed", "tested", "approved", "rejected", "applied", "rolled_back"}
VALID_TRANSITIONS = {
    "proposed": {"sandboxed", "rejected"},
    "sandboxed": {"tested", "rejected"},
    "tested": {"sandboxed", "approved", "rejected"},
    "approved": {"tested", "applied", "rejected"},
    "applied": {"rolled_back"},
    "rejected": set(),
    "rolled_back": {"sandboxed"},
}


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
    policy = classify_change(target)
    now = int(time.time())
    item = {
        "id": "proposal_" + uuid.uuid4().hex[:12],
        "title": str(title)[:200],
        "rationale": str(rationale)[:4000],
        "target": str(target)[:300],
        "risk": risk if risk in {"low", "medium", "high"} else "medium",
        "policy": policy,
        "state": "proposed",
        "created_at": now,
        "updated_at": now,
        "artifacts": [],
        "tests": [],
        "history": [{"state": "proposed", "time": now, "note": "Proposal created."}],
    }
    rows = _read()
    rows.append(item)
    _write(rows[-1000:])
    return item


def record_test(proposal_id: str, name: str, passed: bool, details: str | None = None):
    rows = _read()
    item = next((x for x in rows if x.get("id") == proposal_id), None)
    if not item:
        raise KeyError("Proposal not found.")
    test = {"name": str(name)[:200], "passed": bool(passed), "details": str(details or "")[:2000], "time": int(time.time())}
    item.setdefault("tests", []).append(test)
    item["updated_at"] = test["time"]
    _write(rows)
    return test


def transition(proposal_id: str, state: str, note: str | None = None, approved: bool = False):
    if state not in ALLOWED_STATES:
        raise ValueError("Invalid self-development state.")
    rows = _read()
    item = next((x for x in rows if x.get("id") == proposal_id), None)
    if not item:
        raise KeyError("Proposal not found.")

    current = item.get("state", "proposed")
    if state == current:
        return item
    if state not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid self-development transition: {current} -> {state}.")
    if not allow_self_development_transition(item.get("target", ""), state, approved=approved):
        raise PermissionError("Safety Kernel requires explicit approval for this transition.")

    if state == "approved":
        tests = item.get("tests", [])
        if tests and not all(bool(test.get("passed")) for test in tests):
            raise ValueError("Proposal has failed tests and cannot be approved.")

    now = int(time.time())
    item["state"] = state
    item["updated_at"] = now
    item["policy"] = classify_change(item.get("target", ""))
    item.setdefault("history", []).append({"state": state, "time": now, "note": str(note or "")[:2000], "approved": bool(approved)})
    if note:
        item.setdefault("notes", []).append({"time": now, "text": str(note)})
    _write(rows)
    return item


def list_proposals(limit: int = 100):
    return list(reversed(_read()[-max(1, min(limit, 500)):]))
