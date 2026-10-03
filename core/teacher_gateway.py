from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from cloudru import CloudRuError, foundation_chat, foundation_status

ROOT = Path(__file__).resolve().parent.parent
TEACHER_DIR = ROOT / "data" / "brain" / "teacher"
FEEDBACK_FILE = TEACHER_DIR / "feedback.json"


def _read() -> list[dict]:
    try:
        data = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write(rows: list[dict]) -> None:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FEEDBACK_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows[-2000:], ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(FEEDBACK_FILE)


def status() -> dict:
    cloud = foundation_status()
    rows = _read()
    recent = rows[-1] if rows else None
    return {
        "role": "cloud-teacher",
        "configured": bool(cloud.get("configured")),
        "enabled": bool(cloud.get("enabled")),
        "auto_review": bool(cloud.get("auto_review")),
        "model": cloud.get("model"),
        "feedback_count": len(rows),
        "last_feedback_at": int(recent.get("time", 0)) if recent else 0,
        "policy": {
            "replaces_student_response": False,
            "writes_directly_to_memory": False,
            "auto_promotes_models": False,
            "paid_calls_require_configuration": True,
        },
    }


def _extract_content(response: dict) -> str:
    try:
        return str(response.get("choices", [])[0].get("message", {}).get("content", "")).strip()
    except (AttributeError, IndexError, TypeError):
        return ""


def _parse_json_object(text: str) -> dict:
    text = str(text or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(text[start : end + 1])
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            pass
    return {"summary": text[:4000], "parse_warning": True}


def review(message: str, student_reply: str, context: dict | None = None, session_id: str | None = None, source: str = "manual") -> dict:
    cloud = foundation_status()
    if not cloud.get("configured"):
        raise CloudRuError("Cloud Teacher не настроен.")
    if not cloud.get("enabled"):
        raise CloudRuError("Cloud Teacher отключён.")

    context = context or {}
    memory_items = context.get("memory", {}).get("items", [])[:8]
    memory_summary = [str(item.get("text", ""))[:300] for item in memory_items if item.get("text")]
    situational = {
        "project": (context.get("project") or {}).get("name") if isinstance(context.get("project"), dict) else None,
        "task": (context.get("task") or {}).get("title") if isinstance(context.get("task"), dict) else None,
        "memory": memory_summary,
    }

    system = (
        "Ты Cloud Teacher для личной AI Miyori Kitsune. "
        "Ты не являешься Miyori и не должен подменять её ответ пользователю. "
        "Твоя задача — дать краткий обучающий сигнал по уже сформированному ответу Miyori. "
        "Не раскрывай скрытые рассуждения. Верни только JSON-объект со структурой: "
        '{"summary":"...", "strengths":["..."], "issues":["..."], "corrections":["..."], '
        '"lessons":["..."], "recommended_answer":"...", "confidence":0.0, "tags":["..."]}. '
        "Если ответ корректен, issues/corrections могут быть пустыми."
    )
    user = (
        "Контекст Miyori:\n"
        + json.dumps(situational, ensure_ascii=False)
        + "\n\nСообщение пользователя:\n"
        + str(message)
        + "\n\nОтвет Miyori Student/Brain:\n"
        + str(student_reply)
    )

    response = foundation_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=cloud.get("model"),
        max_tokens=1000,
        temperature=0.1,
    )
    content = _extract_content(response)
    feedback = _parse_json_object(content)
    now = int(time.time())
    item = {
        "id": "teacher_" + uuid.uuid4().hex[:12],
        "time": now,
        "session_id": str(session_id or "") or None,
        "source": str(source or "manual")[:80],
        "teacher_model": cloud.get("model"),
        "message": str(message)[:4000],
        "student_reply": str(student_reply)[:8000],
        "feedback": feedback,
        "usage": response.get("usage", {}) if isinstance(response, dict) else {},
        "accepted_for_training": False,
        "reviewed_by_user": False,
    }
    rows = _read()
    rows.append(item)
    _write(rows)
    return item


def review_if_enabled(message: str, student_reply: str, context: dict | None = None, session_id: str | None = None) -> dict | None:
    cloud = foundation_status()
    if not (cloud.get("configured") and cloud.get("enabled") and cloud.get("auto_review")):
        return None
    try:
        return review(message, student_reply, context=context, session_id=session_id, source="auto-review")
    except Exception as exc:
        return {
            "id": None,
            "time": int(time.time()),
            "source": "auto-review",
            "error": str(exc),
            "accepted_for_training": False,
        }


def list_feedback(limit: int = 100) -> list[dict]:
    rows = _read()
    return list(reversed(rows[-max(1, min(int(limit), 500)):]))


def mark_feedback(feedback_id: str, accepted_for_training: bool, reviewed_by_user: bool = True) -> dict:
    rows = _read()
    item = next((row for row in rows if row.get("id") == feedback_id), None)
    if not item:
        raise KeyError("Teacher feedback not found.")
    item["accepted_for_training"] = bool(accepted_for_training)
    item["reviewed_by_user"] = bool(reviewed_by_user)
    item["reviewed_at"] = int(time.time())
    _write(rows)
    return item
