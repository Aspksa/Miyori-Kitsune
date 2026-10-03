from __future__ import annotations

from cloudru import credentials_status as cloudru_status
from embodiment import status as embodiment_status
from identity import get_identity
from learning import list_learning
from model_evaluation import latest_reports
from model_registry import list_models, summary as model_summary
from neural_runtime import runtime_status
from semantic_memory import status as semantic_memory_status
from reflection import list_reflections
from self_development import list_proposals
from skills import registry
from sleep_engine import consolidate
from training_data import list_datasets
from teacher_gateway import list_feedback as list_teacher_feedback, status as teacher_status
from world_model import snapshot

def architecture_state():
    world = snapshot()
    return {
        "identity": get_identity(),
        "world_model": {
            "nodes": world.get("nodes", {}),
            "edges": world.get("edges", []),
            "updated_at": world.get("updated_at", 0),
        },
        "skills": registry(),
        "learning": list_learning(100),
        "reflections": list_reflections(100),
        "self_development": list_proposals(100),
        "models": {
            "summary": model_summary(),
            "items": list_models(),
            "runtime": runtime_status(),
            "evaluations": latest_reports(20),
        },
        "memory_engine": semantic_memory_status(),
        "teacher": {
            "status": teacher_status(),
            "feedback": list_teacher_feedback(20),
        },
        "embodiment": embodiment_status(),
        "training": {
            "cloudru": cloudru_status(),
            "datasets": list_datasets(20),
        },
    }

def consolidate_now():
    return consolidate()


def overview_state():
    world = snapshot()
    learning = list_learning(500)
    reflections = list_reflections(500)
    skills = registry()
    proposals = list_proposals(500)
    datasets = list_datasets(100)
    cloud = cloudru_status()
    return {
        "identity": get_identity(),
        "world_model": {
            "nodes": len(world.get("nodes", {})),
            "edges": len(world.get("edges", [])),
        },
        "skills": {
            "count": len(skills),
            "enabled": sum(1 for item in skills.values() if item.get("enabled", True)),
        },
        "learning": {
            "count": len(learning),
            "confirmed": sum(1 for item in learning if item.get("stage") in {"confirmed", "retained", "applied", "reassessed"}),
        },
        "reflections": {"count": len(reflections)},
        "development": {
            "count": len(proposals),
            "active": sum(1 for item in proposals if item.get("state") not in {"rejected", "applied", "rolled_back"}),
        },
        "models": {**model_summary(), "runtime": runtime_status(), "evaluations": len(latest_reports(100))},
        "memory_engine": semantic_memory_status(),
        "teacher": teacher_status(),
        "embodiment": embodiment_status(),
        "training": {
            "cloudru": cloud,
            "datasets": len(datasets),
            "latest_dataset": datasets[0] if datasets else None,
        },
    }
