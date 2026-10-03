from __future__ import annotations

import base64
import ctypes
import json
import os
import platform
import time
import urllib.error
import urllib.request
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = ROOT / "data" / "secrets"
CREDENTIALS_FILE = SECRETS_DIR / "cloudru.json"
DATASETS_DIR = ROOT / "data" / "training" / "datasets"
JOBS_FILE = ROOT / "data" / "training" / "cloudru-jobs.json"

API_BASE = "https://api.ai.cloud.ru/public/v2"
SERVICE_AUTH_URL = API_BASE + "/service_auth"
FOUNDATION_API_BASE = "https://foundation-models.api.cloud.ru/v1"
DEFAULT_TEACHER_MODEL = "openai/gpt-oss-120b"


class CloudRuError(RuntimeError):
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_encrypt(value: str) -> str:
    raw = value.encode("utf-8")
    if platform.system() != "Windows":
        return "plain:" + base64.b64encode(raw).decode("ascii")
    blob_in = DATA_BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), "Miyori Cloud.ru", None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise CloudRuError("Не удалось зашифровать секрет через Windows DPAPI.")
    try:
        encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return "dpapi:" + base64.b64encode(encrypted).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_decrypt(value: str) -> str:
    if value.startswith("plain:"):
        return base64.b64decode(value[6:]).decode("utf-8")
    if not value.startswith("dpapi:"):
        return ""
    if platform.system() != "Windows":
        raise CloudRuError("DPAPI-секрет доступен только на Windows, где он был сохранён.")
    encrypted = base64.b64decode(value[6:])
    blob_in = DATA_BLOB(len(encrypted), ctypes.cast(ctypes.create_string_buffer(encrypted), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise CloudRuError("Не удалось расшифровать Cloud.ru секрет.")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _read_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def save_credentials(payload: dict) -> dict:
    current = _read_json(CREDENTIALS_FILE, {})
    key_id = str(payload.get("key_id", current.get("key_id", ""))).strip()
    workspace_id = str(payload.get("workspace_id", current.get("workspace_id", ""))).strip()
    api_key = str(payload.get("api_key", "")).strip()
    key_secret = str(payload.get("key_secret", "")).strip()
    foundation_api_key = str(payload.get("foundation_api_key", "")).strip()

    data = {
        "key_id": key_id,
        "workspace_id": workspace_id,
        "region": str(payload.get("region", current.get("region", "SR006"))).strip() or "SR006",
        "updated_at": int(time.time()),
        "api_base": API_BASE,
        "foundation_api_base": FOUNDATION_API_BASE,
        "teacher_model": str(payload.get("teacher_model", current.get("teacher_model", DEFAULT_TEACHER_MODEL))).strip() or DEFAULT_TEACHER_MODEL,
        "teacher_enabled": bool(payload.get("teacher_enabled", current.get("teacher_enabled", True))),
        "teacher_auto_review": bool(payload.get("teacher_auto_review", current.get("teacher_auto_review", False))),
    }
    data["api_key"] = _dpapi_encrypt(api_key) if api_key else current.get("api_key", "")
    data["key_secret"] = _dpapi_encrypt(key_secret) if key_secret else current.get("key_secret", "")
    data["foundation_api_key"] = _dpapi_encrypt(foundation_api_key) if foundation_api_key else current.get("foundation_api_key", "")

    training_values = [data.get("key_id"), data.get("key_secret"), data.get("workspace_id"), data.get("api_key")]
    if any(training_values) and not all(training_values):
        raise ValueError("Для Cloud.ru GPU Training заполните Key ID, Key Secret, Workspace ID и x-api-key полностью.")
    if not all(training_values) and not data.get("foundation_api_key"):
        raise ValueError("Настройте Cloud.ru GPU Training или укажите Foundation Models API Key для Cloud Teacher.")

    _write_json(CREDENTIALS_FILE, data)
    return credentials_status()


def credentials_status() -> dict:
    data = _read_json(CREDENTIALS_FILE, {})
    training_configured = all(data.get(k) for k in ("key_id", "key_secret", "workspace_id", "api_key"))
    foundation_configured = bool(data.get("foundation_api_key"))
    return {
        "configured": bool(training_configured),
        "training_configured": bool(training_configured),
        "foundation_configured": foundation_configured,
        "key_id": str(data.get("key_id", "")),
        "workspace_id": str(data.get("workspace_id", "")),
        "region": str(data.get("region", "SR006")),
        "secret_saved": bool(data.get("key_secret")),
        "api_key_saved": bool(data.get("api_key")),
        "foundation_api_key_saved": foundation_configured,
        "teacher_model": str(data.get("teacher_model", DEFAULT_TEACHER_MODEL) or DEFAULT_TEACHER_MODEL),
        "teacher_enabled": bool(data.get("teacher_enabled", True)),
        "teacher_auto_review": bool(data.get("teacher_auto_review", False)),
        "foundation_api_base": FOUNDATION_API_BASE,
        "storage": "windows-dpapi" if platform.system() == "Windows" else "local-file-0600",
        "updated_at": int(data.get("updated_at", 0) or 0),
    }


def _credentials() -> dict:
    data = _read_json(CREDENTIALS_FILE, {})
    if not all(data.get(k) for k in ("key_id", "key_secret", "workspace_id", "api_key")):
        raise CloudRuError("Cloud.ru GPU Training ещё не настроен в Личном кабинете.")
    return {
        **data,
        "key_secret": _dpapi_decrypt(data["key_secret"]),
        "api_key": _dpapi_decrypt(data["api_key"]),
    }


def _foundation_credentials() -> dict:
    data = _read_json(CREDENTIALS_FILE, {})
    if not data.get("foundation_api_key"):
        raise CloudRuError("Cloud Teacher не настроен. Добавьте Foundation Models API Key в Личном кабинете.")
    return {
        "api_key": _dpapi_decrypt(data["foundation_api_key"]),
        "model": str(data.get("teacher_model", DEFAULT_TEACHER_MODEL) or DEFAULT_TEACHER_MODEL),
        "enabled": bool(data.get("teacher_enabled", True)),
        "auto_review": bool(data.get("teacher_auto_review", False)),
    }


def foundation_status() -> dict:
    status = credentials_status()
    return {
        "configured": status["foundation_configured"],
        "enabled": status["teacher_enabled"],
        "auto_review": status["teacher_auto_review"],
        "model": status["teacher_model"],
        "api_key_saved": status["foundation_api_key_saved"],
        "api_base": FOUNDATION_API_BASE,
    }


def _foundation_headers() -> dict:
    creds = _foundation_credentials()
    return {"Authorization": "Bearer " + creds["api_key"]}


def foundation_models():
    return _request(FOUNDATION_API_BASE + "/models", headers=_foundation_headers())


def foundation_chat(messages: list[dict], model: str | None = None, max_tokens: int = 800, temperature: float = 0.2) -> dict:
    creds = _foundation_credentials()
    if not creds["enabled"]:
        raise CloudRuError("Cloud Teacher отключён в Личном кабинете.")
    selected_model = str(model or creds["model"]).strip() or DEFAULT_TEACHER_MODEL
    payload = {
        "model": selected_model,
        "messages": messages,
        "max_tokens": max(64, min(int(max_tokens), 4000)),
        "temperature": max(0.0, min(float(temperature), 2.0)),
    }
    return _request(
        FOUNDATION_API_BASE + "/chat/completions",
        method="POST",
        headers=_foundation_headers(),
        payload=payload,
        timeout=90,
    )


def test_foundation_connection() -> dict:
    started = time.time()
    data = foundation_models()
    rows = data.get("data", []) if isinstance(data, dict) else []
    configured = foundation_status()
    model_ids = {str(item.get("id")) for item in rows if isinstance(item, dict)}
    return {
        "connected": True,
        "latency_ms": int((time.time() - started) * 1000),
        "models_found": len(rows),
        "selected_model_available": configured["model"] in model_ids if model_ids else None,
        "status": configured,
    }


def access_token() -> str:
    creds = _credentials()
    data = _request(
        SERVICE_AUTH_URL,
        method="POST",
        payload={"client_id": creds["key_id"], "client_secret": creds["key_secret"]},
    )
    token = str(data.get("access_token") or data.get("token") or "")
    if not token:
        raise CloudRuError("Cloud.ru не вернул access token.")
    return token


def _auth_headers() -> dict:
    creds = _credentials()
    return {
        "Authorization": access_token(),
        "X-Api-Key": creds["api_key"],
        "X-Workspace-Id": creds["workspace_id"],
    }


def test_connection() -> dict:
    started = time.time()
    data = _request(API_BASE + "/configs?cluster_type=MT", headers=_auth_headers())
    return {
        "connected": True,
        "latency_ms": int((time.time() - started) * 1000),
        "configs_found": len(data) if isinstance(data, list) else len(data.get("items", data.get("configs", []))) if isinstance(data, dict) else 0,
        "status": credentials_status(),
    }


def list_training_configs():
    return _request(API_BASE + "/configs?cluster_type=MT", headers=_auth_headers())


def submit_training_job(spec: dict) -> dict:
    required = ("base_image", "script", "region", "instance_type", "type")
    missing = [name for name in required if not str(spec.get(name, "")).strip()]
    if missing:
        raise ValueError("Не хватает параметров training job: " + ", ".join(missing))

    payload = {
        "base_image": spec["base_image"],
        "script": spec["script"],
        "region": spec["region"],
        "instance_type": spec["instance_type"],
        "type": spec["type"],
        "n_workers": int(spec.get("n_workers", 1)),
        "job_desc": str(spec.get("job_desc", "Miyori Kitsune training"))[:500],
    }
    for optional in ("allocation_name", "queue_name", "priority_class"):
        if spec.get(optional):
            payload[optional] = spec[optional]

    result = _request(API_BASE + "/jobs", method="POST", headers=_auth_headers(), payload=payload, timeout=60)
    rows = _read_json(JOBS_FILE, [])
    if not isinstance(rows, list):
        rows = []
    rows.append({"created_at": int(time.time()), "request": payload, "response": result})
    _write_json(JOBS_FILE, rows[-500:])
    return result


def job_history(limit: int = 100) -> list[dict]:
    rows = _read_json(JOBS_FILE, [])
    return list(reversed(rows[-max(1, min(limit, 500)):])) if isinstance(rows, list) else []
