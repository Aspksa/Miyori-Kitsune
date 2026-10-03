from __future__ import annotations

from cloudru import credentials_status as cloudru_status
from identity import get_identity
from learning import list_learning
from reflection import list_reflections
from self_development import list_proposals
from skills import registry
from sleep_engine import consolidate
from training_data import list_datasets
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
        "training": {
            "cloudru": cloudru_status(),
            "datasets": list_datasets(20),
        },
    }

def consolidate_now():
    return consolidate()
