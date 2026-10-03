from __future__ import annotations

from cloudru import student_status as cloud_student_status
from model_registry import list_models, register_model, rollback_active, summary as model_registry_summary, transition


def model_id_for(version: str) -> str:
    safe = "".join(ch for ch in str(version or "0.1.0") if ch.isalnum() or ch in ".-_")[:48] or "0.1.0"
    return f"miyori-cloud-student@{safe}"


def current_model() -> dict | None:
    cloud = cloud_student_status()
    wanted = model_id_for(cloud.get("version", "0.1.0"))
    return next((item for item in list_models() if item.get("id") == wanted), None)


def validate_configuration_change(payload: dict) -> None:
    cloud = cloud_student_status()
    incoming_version = str(payload.get("student_version", cloud.get("version", "0.1.0")) or "0.1.0").strip()
    incoming_id = model_id_for(incoming_version)
    item = next((row for row in list_models() if row.get("id") == incoming_id), None)
    if not item or item.get("stage") != "active":
        return
    metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
    incoming_endpoint = str(payload.get("student_endpoint", cloud.get("endpoint", "")) or "").strip().rstrip("/")
    current_endpoint = str(metadata.get("endpoint") or "").strip().rstrip("/")
    incoming_model = str(payload.get("student_model", cloud.get("model", "")) or "").strip()
    current_model_name = str(metadata.get("model_name") or "").strip()
    if incoming_endpoint != current_endpoint or incoming_model != current_model_name:
        raise ValueError("Активную версию Miyori Student нельзя заменить без новой версии. Увеличьте Student version, затем пройдите evaluation и активацию.")


def register_current() -> dict:
    cloud = cloud_student_status()
    if not cloud.get("configured"):
        raise ValueError("Miyori Student ещё не настроен в Cloud.ru ML Inference.")
    model_id = model_id_for(cloud.get("version", "0.1.0"))
    existing = next((item for item in list_models() if item.get("id") == model_id), None)
    if existing:
        metadata = existing.get("metadata", {}) if isinstance(existing.get("metadata"), dict) else {}
        changed = (
            str(metadata.get("endpoint") or "") != str(cloud.get("endpoint") or "")
            or str(metadata.get("model_name") or "") != str(cloud.get("model") or "")
        )
        if changed and existing.get("stage") == "active":
            raise ValueError("Нельзя менять endpoint или model активной версии Student. Увеличьте версию Student и сохраните её как новый candidate.")
    item = register_model(
        model_id=model_id,
        name="miyori-cloud-student",
        version=str(cloud.get("version", "0.1.0")),
        runtime="cloud_ml_inference",
        artifact_path=None,
        metadata={
            "provider": "cloudru-ml-inference",
            "model_name": cloud.get("model"),
            "endpoint": cloud.get("endpoint"),
            "role": "miyori-student",
            "trainable": True,
            "personal": True,
            "teacher": False,
        },
    )
    if existing:
        old_metadata = existing.get("metadata", {}) if isinstance(existing.get("metadata"), dict) else {}
        changed = (
            str(old_metadata.get("endpoint") or "") != str(cloud.get("endpoint") or "")
            or str(old_metadata.get("model_name") or "") != str(cloud.get("model") or "")
        )
        if changed:
            item["metrics"] = {}
            from model_registry import update_metrics
            item = update_metrics(item["id"], {})
            if item.get("stage") == "approved":
                item = transition(item["id"], "testing")
    return item


def prepare_for_evaluation() -> dict:
    item = current_model() or register_current()
    if item.get("stage") == "candidate":
        item = transition(item["id"], "testing")
    elif item.get("stage") not in {"testing", "approved", "active"}:
        raise ValueError(f"Student в состоянии {item.get('stage')} нельзя подготовить к оценке.")
    return item


def promote_current(approved: bool = False, min_score: float = 0.75) -> dict:
    if not approved:
        raise PermissionError("Активация Miyori Student требует явного подтверждения.")
    item = current_model()
    if not item:
        raise ValueError("Student candidate не зарегистрирован.")
    score = float((item.get("metrics") or {}).get("evaluation_score", 0) or 0)
    if score < float(min_score):
        raise ValueError(f"Student не прошёл минимальную оценку: {score:.2f} < {float(min_score):.2f}.")
    stage = item.get("stage")
    if stage == "candidate":
        item = transition(item["id"], "testing")
        stage = item.get("stage")
    if stage == "testing":
        item = transition(item["id"], "approved")
        stage = item.get("stage")
    if stage == "approved":
        item = transition(item["id"], "active", approved=True)
    elif stage != "active":
        raise ValueError(f"Student нельзя активировать из состояния {stage}.")
    return item


def rollback_current(approved: bool = False) -> dict:
    if not approved:
        raise PermissionError("Rollback Miyori Student требует явного подтверждения.")
    return rollback_active(approved=True)


def status() -> dict:
    cloud = cloud_student_status()
    item = current_model()
    registry = model_registry_summary()
    active = registry.get("active") or {}
    active_is_student = active.get("runtime") == "cloud_ml_inference"
    return {
        **cloud,
        "registry_model": item,
        "registry_model_id": item.get("id") if item else model_id_for(cloud.get("version", "0.1.0")),
        "stage": item.get("stage") if item else "unregistered",
        "evaluation_score": (item.get("metrics") or {}).get("evaluation_score") if item else None,
        "rollback_available": bool(registry.get("rollback_available")),
        "active_model_id": active.get("id"),
        "active_is_student": active_is_student,
        "active_student_version": active.get("version") if active_is_student else None,
        "active_student_stage": active.get("stage") if active_is_student else None,
        "policy": {
            "teacher_is_separate": True,
            "activation_requires_explicit_approval": True,
            "actions_remain_in_action_gateway": True,
            "fallback": "miyori-internal-planner",
        },
    }
