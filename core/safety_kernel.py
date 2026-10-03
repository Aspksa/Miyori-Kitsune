from __future__ import annotations

CRITICAL_TARGET_PREFIXES = (
    "core/server.py",
    "core/updater.py",
    "core/safety_kernel.py",
    "core/assistant_gateway.py",
    "core/brain.py",
    "core/brain_runtime.py",
    "core/model_registry.py",
    "core/embodiment.py",
    "core/memory.py",
    "MiyoriKitsune.bat",
)


def classify_change(target: str) -> dict:
    target = str(target)
    critical = any(target.startswith(prefix) for prefix in CRITICAL_TARGET_PREFIXES)
    return {
        "target": target,
        "critical": critical,
        "requires_human_approval": critical,
        "requires_tests": True,
        "requires_backup": True,
        "direct_self_apply": False,
        "apply_requires_explicit_approval": True,
    }


def allow_self_development_transition(target: str, state: str, approved: bool = False) -> bool:
    policy = classify_change(target)
    if state not in {"proposed", "sandboxed", "tested", "approved", "rejected", "applied", "rolled_back"}:
        return False
    if state == "approved" and policy["requires_human_approval"] and not approved:
        return False
    if state == "applied" and not approved:
        return False
    return True
