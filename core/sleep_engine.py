from __future__ import annotations

import time

from learning import list_learning
from reflection import list_reflections
from skills import registry
from world_model import snapshot

def consolidate():
    world = snapshot()
    reflections = list_reflections(200)
    learning = list_learning(200)
    skills = registry()
    return {
        "time": int(time.time()),
        "world_nodes": len(world.get("nodes", {})),
        "world_edges": len(world.get("edges", [])),
        "reflections": len(reflections),
        "learning_items": len(learning),
        "skills": len(skills),
        "recommendations": _recommend(world, reflections, learning),
    }

def _recommend(world, reflections, learning):
    recommendations = []
    if not world.get("nodes"):
        recommendations.append("Build more world-model observations from projects, tasks and memory.")
    if not reflections:
        recommendations.append("Run reflection after completed action cycles.")
    if learning and all(item.get("stage") == "observed" for item in learning[:20]):
        recommendations.append("Confirm repeated observations before promoting them to retained knowledge.")
    return recommendations
