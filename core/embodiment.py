from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "data" / "brain" / "embodiment.json"

_CHANNELS = {
    "vision": {"label": "Глаза", "kind": "sensor", "purpose": "Изображения, экран, камера и визуальное окружение.", "enabled": True, "hardware_connected": False, "adapters": ["chat-image"]},
    "hearing": {"label": "Уши", "kind": "sensor", "purpose": "Аудио, микрофон и распознавание речи.", "enabled": False, "hardware_connected": False, "adapters": []},
    "speech": {"label": "Голос", "kind": "actuator", "purpose": "Синтез речи и звуковой ответ.", "enabled": False, "hardware_connected": False, "adapters": []},
    "hands": {"label": "Руки", "kind": "actuator", "purpose": "Управляемые цифровые действия через Action Gateway и будущие computer tools.", "enabled": True, "hardware_connected": True, "adapters": ["action-gateway"]},
    "mobility": {"label": "Ноги", "kind": "actuator", "purpose": "Навигация и перемещение в цифровой или физической среде через отдельный адаптер.", "enabled": False, "hardware_connected": False, "adapters": []},
}


def _default() -> dict:
    return {"schema_version": 1, "channels": {key: dict(value) for key, value in _CHANNELS.items()}, "observations": [], "updated_at": 0}


def _read() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default()
    except (OSError, json.JSONDecodeError):
        return _default()
    channels = data.get("channels", {})
    if not isinstance(channels, dict):
        channels = {}
    for key, defaults in _CHANNELS.items():
        current = channels.get(key, {})
        if not isinstance(current, dict):
            current = {}
        merged = dict(defaults)
        merged.update(current)
        merged["adapters"] = list(dict.fromkeys(merged.get("adapters", [])))
        channels[key] = merged
    data["channels"] = channels
    data["observations"] = [row for row in data.get("observations", []) if isinstance(row, dict)][-200:]
    data.setdefault("schema_version", 1)
    data.setdefault("updated_at", 0)
    return data


def _write(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATE_FILE)


def status() -> dict:
    state = _read()
    channels = state["channels"]
    return {
        "channels": channels,
        "sensors_enabled": sum(1 for item in channels.values() if item.get("kind") == "sensor" and item.get("enabled")),
        "actuators_enabled": sum(1 for item in channels.values() if item.get("kind") == "actuator" and item.get("enabled")),
        "hardware_connected": sum(1 for item in channels.values() if item.get("hardware_connected")),
        "recent_observations": len(state.get("observations", [])),
        "updated_at": int(state.get("updated_at", 0)),
        "policy": {"hardware_access_requires_adapter": True, "actuation_requires_gateway": True, "physical_mobility_default": "disabled"},
    }


def configure_channel(channel: str, enabled: bool | None = None, hardware_connected: bool | None = None, adapters: list[str] | None = None) -> dict:
    state = _read()
    if channel not in state["channels"]:
        raise ValueError("Unknown embodiment channel.")
    item = state["channels"][channel]
    if enabled is not None:
        item["enabled"] = bool(enabled)
    if hardware_connected is not None:
        item["hardware_connected"] = bool(hardware_connected)
    if adapters is not None:
        item["adapters"] = list(dict.fromkeys(str(value).strip() for value in adapters if str(value).strip()))
    state["updated_at"] = int(time.time())
    _write(state)
    return item


def record_observation(channel: str, summary: str, source: str = "runtime", metadata: dict | None = None) -> dict:
    state = _read()
    if channel not in state["channels"]:
        raise ValueError("Unknown embodiment channel.")
    channel_state = state["channels"][channel]
    if channel_state.get("kind") != "sensor":
        raise ValueError("Observations can only be recorded for sensor channels.")
    if not channel_state.get("enabled"):
        raise PermissionError("Sensor channel is disabled.")
    item = {"channel": channel, "summary": str(summary)[:2000], "source": str(source)[:120], "metadata": metadata if isinstance(metadata, dict) else {}, "time": int(time.time())}
    state["observations"].append(item)
    state["observations"] = state["observations"][-200:]
    state["updated_at"] = item["time"]
    _write(state)
    return item


def perception_manifest() -> dict:
    state = status()
    return {
        "channels": {
            key: {"label": value.get("label"), "kind": value.get("kind"), "enabled": bool(value.get("enabled")), "hardware_connected": bool(value.get("hardware_connected")), "adapters": value.get("adapters", [])}
            for key, value in state["channels"].items()
        },
        "policy": state["policy"],
    }
