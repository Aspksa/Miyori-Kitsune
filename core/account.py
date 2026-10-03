from __future__ import annotations

import json
import platform
import secrets
import socket
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROFILE_FILE = DATA_DIR / "profile.json"
DEVICES_FILE = DATA_DIR / "devices.json"
PAIRING_FILE = DATA_DIR / "pairing.json"

DEFAULT_PROFILE = {
    "display_name": "Aspksa",
    "language": "ru",
    "theme": "dark",
    "notifications": True,
    "sync_enabled": False,
    "lock_enabled": False,
}


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def get_profile() -> dict:
    stored = _read_json(PROFILE_FILE, {})
    profile = {**DEFAULT_PROFILE, **stored}
    profile["profile_id"] = str(profile.get("profile_id") or uuid.uuid4())
    if profile != stored:
        _write_json(PROFILE_FILE, profile)
    return profile


def save_profile(payload: dict) -> dict:
    profile = get_profile()
    allowed = {
        "display_name": str,
        "language": str,
        "theme": str,
        "notifications": bool,
        "sync_enabled": bool,
        "lock_enabled": bool,
    }
    for key, kind in allowed.items():
        if key in payload and isinstance(payload[key], kind):
            profile[key] = payload[key]
    profile["display_name"] = profile["display_name"].strip()[:64] or "Aspksa"
    if profile["language"] not in {"ru", "en"}:
        profile["language"] = "ru"
    if profile["theme"] not in {"dark", "light", "system"}:
        profile["theme"] = "dark"
    _write_json(PROFILE_FILE, profile)
    return profile


def _current_device() -> dict:
    return {
        "id": "local-desktop",
        "name": socket.gethostname() or "Miyori PC",
        "type": "desktop",
        "platform": platform.system() or "Windows",
        "current": True,
        "status": "online",
        "last_seen": int(time.time()),
    }


def list_devices() -> list[dict]:
    devices = _read_json(DEVICES_FILE, [])
    if not isinstance(devices, list):
        devices = []
    clean = [d for d in devices if isinstance(d, dict) and d.get("id") != "local-desktop"]
    return [_current_device(), *clean]


def revoke_device(device_id: str) -> bool:
    if not device_id or device_id == "local-desktop":
        return False
    devices = _read_json(DEVICES_FILE, [])
    if not isinstance(devices, list):
        devices = []
    updated = [d for d in devices if d.get("id") != device_id]
    changed = len(updated) != len(devices)
    if changed:
        _write_json(DEVICES_FILE, updated)
    return changed


def create_pairing() -> dict:
    code = f"{secrets.randbelow(1000000):06d}"
    token = secrets.token_urlsafe(24)
    expires_at = int(time.time()) + 300
    data = {
        "code": code,
        "token": token,
        "expires_at": expires_at,
        "created_at": int(time.time()),
    }
    _write_json(PAIRING_FILE, data)
    return {
        "code": code,
        "expires_at": expires_at,
        "pairing_uri": f"miyori://pair?code={code}&token={token}",
    }


def pairing_status() -> dict:
    data = _read_json(PAIRING_FILE, {})
    expires_at = int(data.get("expires_at") or 0)
    active = bool(data.get("code")) and expires_at > int(time.time())
    return {
        "active": active,
        "code": str(data.get("code", "")) if active else "",
        "expires_at": expires_at if active else 0,
    }
