from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from learning import list_learning
from reflection import list_reflections
from teacher_gateway import list_feedback as list_teacher_feedback

ROOT = Path(__file__).resolve().parent.parent
BRAIN_DIR = ROOT / "data" / "brain"
SESSIONS_DIR = BRAIN_DIR / "sessions"
DATASETS_DIR = ROOT / "data" / "training" / "datasets"
MANIFEST_FILE = ROOT / "data" / "training" / "datasets.json"

ALLOWED_LEARNING_STAGES = {"confirmed", "retained", "applied", "reassessed"}


def _read_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _session_examples(limit: int = 500) -> list[dict]:
    examples = []
    if not SESSIONS_DIR.exists():
        return examples
    for path in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        data = _read_json(path, {})
        messages = data.get("messages", []) if isinstance(data, dict) else []
        for i in range(len(messages) - 1):
            first, second = messages[i], messages[i + 1]
            if first.get("role") != "user" or second.get("role") != "assistant":
                continue
            meta = second.get("meta", {})
            if meta.get("intent") == "conversation":
                continue
            examples.append({
                "type": "interaction",
                "input": str(first.get("content", "")),
                "output": str(second.get("content", "")),
                "metadata": {
                    "intent": meta.get("intent"),
                    "source": "miyori-session",
                    "session_id": data.get("id"),
                },
            })
            if len(examples) >= limit:
                return examples
    return examples


def build_dataset(name: str = "miyori-learning", include_sessions: bool = True) -> dict:
    now = int(time.time())
    dataset_id = "dataset_" + uuid.uuid4().hex[:12]
    records = []

    for item in list_learning(2000):
        if item.get("stage") not in ALLOWED_LEARNING_STAGES:
            continue
        records.append({
            "type": "learning",
            "input": str(item.get("subject", "")),
            "output": str(item.get("statement", "")),
            "metadata": {
                "stage": item.get("stage"),
                "confidence": item.get("confidence"),
                "source": item.get("source"),
                "evidence": item.get("evidence", []),
            },
        })

    for reflection in list_reflections(1000):
        if float(reflection.get("confidence", 0)) < 0.5:
            continue
        source = reflection.get("source", {})
        records.append({
            "type": "reflection",
            "input": json.dumps({
                "intent": source.get("intent"),
                "actions": source.get("actions", []),
                "outcome": source.get("outcome"),
            }, ensure_ascii=False),
            "output": "\n".join(str(x) for x in reflection.get("lessons", [])),
            "metadata": {
                "confidence": reflection.get("confidence"),
                "source": "reflection-engine",
            },
        })

    for feedback in list_teacher_feedback(2000):
        if not feedback.get("accepted_for_training"):
            continue
        review = feedback.get("feedback", {}) if isinstance(feedback.get("feedback"), dict) else {}
        recommended = str(review.get("recommended_answer", "")).strip()
        if not recommended:
            continue
        records.append({
            "type": "teacher-supervised",
            "input": str(feedback.get("message", "")),
            "output": recommended,
            "metadata": {
                "source": "cloud-teacher",
                "teacher_model": feedback.get("teacher_model"),
                "feedback_id": feedback.get("id"),
                "confidence": review.get("confidence"),
                "lessons": review.get("lessons", []),
                "tags": review.get("tags", []),
            },
        })

    if include_sessions:
        records.extend(_session_examples())

    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    path = DATASETS_DIR / f"{dataset_id}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = _read_json(MANIFEST_FILE, [])
    if not isinstance(manifest, list):
        manifest = []
    item = {
        "id": dataset_id,
        "name": str(name).strip()[:120] or "miyori-learning",
        "path": str(path.relative_to(ROOT)),
        "records": len(records),
        "created_at": now,
        "status": "candidate",
        "cloud_uploaded": False,
    }
    manifest.append(item)
    _write_json(MANIFEST_FILE, manifest[-500:])
    return item


def list_datasets(limit: int = 100) -> list[dict]:
    rows = _read_json(MANIFEST_FILE, [])
    if not isinstance(rows, list):
        return []
    return list(reversed(rows[-max(1, min(limit, 500)):]))

