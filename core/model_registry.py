from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = ROOT / "data" / "brain" / "models" / "registry.json"

MODEL_STAGES = ("candidate", "testing", "approved", "active", "retired", "rolled_back")
BUILTIN_MODEL_ID = "miyori-internal-planner@0.1.0"


def _now() -> int:
    return int(time.time())


def _builtin_model() -> dict:
    return {
        "id": BUILTIN_MODEL_ID,
        "name": "miyori-internal-planner",
        "version": "0.1.0",
        "runtime": "internal",
        "stage": "active",
        "artifact_path": None,
        "metrics": {},
        "metadata": {
            "trainable": False,
            "description": "Built-in planner used until a trained Miyori neural model is promoted.",
        },
        "created_at": 0,
        "updated_at": 0,
    }


def _default() -> dict:
    return {
        "schema_version": 1,
        "active_model_id": BUILTIN_MODEL_ID,
        "previous_active_model_id": None,
        "models": {BUILTIN_MODEL_ID: _builtin_model()},
        "updated_at": 0,
    }


def _read() -> dict:
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default()
    except (OSError, json.JSONDecodeError):
        return _default()

    models = data.get("models", {})
    if not isinstance(models, dict):
        models = {}
    if BUILTIN_MODEL_ID not in models:
        models[BUILTIN_MODEL_ID] = _builtin_model()
    data["models"] = models
    data.setdefault("schema_version", 1)
    data.setdefault("active_model_id", BUILTIN_MODEL_ID)
    data.setdefault("previous_active_model_id", None)
    data.setdefault("updated_at", 0)
    return data


def _write(data: dict) -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = REGISTRY_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(REGISTRY_FILE)


def registry() -> dict:
    return _read()


def list_models() -> list[dict]:
    state = _read()
    rows = list(state["models"].values())
    rows.sort(key=lambda item: int(item.get("updated_at", 0)), reverse=True)
    return rows


def active_model() -> dict:
    state = _read()
    model_id = state.get("active_model_id") or BUILTIN_MODEL_ID
    return state["models"].get(model_id) or _builtin_model()


def register_model(model_id: str, name: str, version: str, runtime: str = "neural", artifact_path: str | None = None, metrics: dict | None = None, metadata: dict | None = None) -> dict:
    model_id = str(model_id).strip()
    name = str(name).strip()
    version = str(version).strip()
    if not model_id or not name or not version:
        raise ValueError("Model id, name and version are required.")
    state = _read()
    now = _now()
    existing = state["models"].get(model_id, {})
    item = {
        "id": model_id,
        "name": name,
        "version": version,
        "runtime": str(runtime or "neural"),
        "stage": existing.get("stage", "candidate"),
        "artifact_path": str(artifact_path).strip() if artifact_path else None,
        "metrics": metrics if isinstance(metrics, dict) else existing.get("metrics", {}),
        "metadata": metadata if isinstance(metadata, dict) else existing.get("metadata", {}),
        "created_at": int(existing.get("created_at", now)),
        "updated_at": now,
    }
    state["models"][model_id] = item
    state["updated_at"] = now
    _write(state)
    return item


def update_metrics(model_id: str, metrics: dict) -> dict:
    state = _read()
    item = state["models"].get(model_id)
    if not item:
        raise KeyError("Model not found.")
    item["metrics"] = metrics if isinstance(metrics, dict) else {}
    item["updated_at"] = _now()
    state["updated_at"] = item["updated_at"]
    _write(state)
    return item


def transition(model_id: str, stage: str, approved: bool = False) -> dict:
    if stage not in MODEL_STAGES:
        raise ValueError("Invalid model stage.")
    state = _read()
    item = state["models"].get(model_id)
    if not item:
        raise KeyError("Model not found.")
    current = item.get("stage", "candidate")
    allowed = {
        "candidate": {"testing", "retired"},
        "testing": {"approved", "candidate", "retired"},
        "approved": {"active", "testing", "retired"},
        "active": {"retired", "rolled_back"},
        "retired": {"testing"},
        "rolled_back": {"testing", "retired"},
    }
    if stage == current:
        return item
    if stage not in allowed.get(current, set()):
        raise ValueError(f"Invalid model transition: {current} -> {stage}.")
    if stage == "active" and not approved:
        raise PermissionError("Activating a model requires explicit approval.")
    now = _now()
    if stage == "active":
        previous_id = state.get("active_model_id")
        if previous_id and previous_id != model_id and previous_id in state["models"]:
            previous = state["models"][previous_id]
            previous["stage"] = "retired"
            previous["updated_at"] = now
            state["previous_active_model_id"] = previous_id
        state["active_model_id"] = model_id
    item["stage"] = stage
    item["updated_at"] = now
    state["updated_at"] = now
    _write(state)
    return item


def rollback_active(approved: bool = False) -> dict:
    if not approved:
        raise PermissionError("Model rollback requires explicit approval.")
    state = _read()
    current_id = state.get("active_model_id")
    previous_id = state.get("previous_active_model_id")
    if not previous_id or previous_id not in state["models"]:
        raise ValueError("No previous model is available for rollback.")
    now = _now()
    if current_id in state["models"]:
        state["models"][current_id]["stage"] = "rolled_back"
        state["models"][current_id]["updated_at"] = now
    state["models"][previous_id]["stage"] = "active"
    state["models"][previous_id]["updated_at"] = now
    state["active_model_id"] = previous_id
    state["previous_active_model_id"] = current_id
    state["updated_at"] = now
    _write(state)
    return state["models"][previous_id]


def summary() -> dict:
    state = _read()
    models = list(state["models"].values())
    return {
        "active": active_model(),
        "count": len(models),
        "candidates": sum(1 for item in models if item.get("stage") in {"candidate", "testing", "approved"}),
        "rollback_available": bool(state.get("previous_active_model_id")),
        "updated_at": int(state.get("updated_at", 0)),
    }
