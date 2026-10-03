from __future__ import annotations

CRITICAL_TARGET_PREFIXES = (
    "core/server.py",
    "core/updater.py",
    "core/safety_kernel.py",
    "core/assistant_gateway.py",
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
    }

def allow_self_development_transition(target: str, state: str, approved: bool = False) -> bool:
    policy = classify_change(target)
    if state in {"approved", "applied"} and policy["requires_human_approval"] and not approved:
        return False
    return state in {"proposed", "sandboxed", "tested", "approved", "rejected", "applied", "rolled_back"}
