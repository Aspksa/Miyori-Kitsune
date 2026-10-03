from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_FILE = ROOT / "data" / "brain" / "skills.json"

BUILTIN_SKILLS = {
    "projects.manage": {"name": "Project Management", "source": "builtin"},
    "tasks.manage": {"name": "Task Management", "source": "builtin"},
    "memory.manage": {"name": "Memory Management", "source": "builtin"},
    "context.resolve": {"name": "Context Resolution", "source": "builtin"},
}

def _read():
    try:
        data = json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def _write(data):
    SKILLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SKILLS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SKILLS_FILE)

def registry():
    data = _read()
    for skill_id, skill in BUILTIN_SKILLS.items():
        data.setdefault(skill_id, {**skill, "enabled": True, "uses": 0, "updated_at": int(time.time())})
    _write(data)
    return data

def record_use(skill_id: str, success: bool = True):
    data = registry()
    skill = data.setdefault(skill_id, {"name": skill_id, "source": "learned", "enabled": True, "uses": 0})
    skill["uses"] = int(skill.get("uses", 0)) + 1
    skill["successes"] = int(skill.get("successes", 0)) + (1 if success else 0)
    skill["updated_at"] = int(time.time())
    _write(data)
    return skill
