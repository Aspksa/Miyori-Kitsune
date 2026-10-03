from __future__ import annotations

import json
import shutil
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = "Aspksa/Miyori-Kitsune"
BRANCH = "main"
ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "version.json"
BACKUP_DIR = ROOT / "backups"
PRESERVE_TOP_LEVEL = {".git", "data", "logs", "backups"}
PRESERVE_FILES = {"config/local.json"}

RAW_VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.json"
ZIP_URL = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"


class UpdateError(RuntimeError):
    pass


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def local_manifest() -> dict:
    data = _read_json(VERSION_FILE)
    return {
        "version": str(data.get("version", "0.0.0")),
        "channel": str(data.get("channel", "stable")),
        "repository": str(data.get("repository", REPO)),
        "components": {str(k): str(v) for k, v in data.get("components", {}).items()},
    }


def local_version() -> str:
    return local_manifest()["version"]


def _fetch_json(url: str, timeout: int = 12) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Miyori-Kitsune-Updater",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise UpdateError(f"Не удалось получить данные обновления: {exc}") from exc


def check_update() -> dict:
    remote = _fetch_json(RAW_VERSION_URL)
    local = local_manifest()
    current = local["version"]
    latest = str(remote.get("version", current))
    local_components = local.get("components", {})
    remote_components = {str(k): str(v) for k, v in remote.get("components", {}).items()}
    component_changes = []
    for name in sorted(set(local_components) | set(remote_components)):
        installed = str(local_components.get(name, "0.0.0"))
        available = str(remote_components.get(name, installed))
        component_changes.append({
            "name": name,
            "current": installed,
            "latest": available,
            "changed": installed != available,
        })
    return {
        "ok": True,
        "current": current,
        "latest": latest,
        "available": latest != current or any(item["changed"] for item in component_changes),
        "channel": str(remote.get("channel", "stable")),
        "repository": REPO,
        "components": component_changes,
    }


def _safe_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _should_preserve(relative: Path) -> bool:
    parts = relative.parts
    if not parts:
        return True
    if parts[0] in PRESERVE_TOP_LEVEL:
        return True
    return relative.as_posix() in PRESERVE_FILES


def _backup_existing(source_root: Path, backup_root: Path) -> int:
    count = 0
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        if _should_preserve(relative):
            continue
        target = backup_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        count += 1
    return count


def apply_update() -> dict:
    status = check_update()
    if not status["available"]:
        return {**status, "updated": False, "restart_required": False}

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_root = BACKUP_DIR / stamp

    with tempfile.TemporaryDirectory(prefix="miyori-update-") as temp:
        temp_dir = Path(temp)
        archive = temp_dir / "update.zip"

        request = urllib.request.Request(ZIP_URL, headers={"User-Agent": "Miyori-Kitsune-Updater"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                archive.write_bytes(response.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpdateError(f"Не удалось скачать обновление: {exc}") from exc

        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(temp_dir / "src")
        except (zipfile.BadZipFile, OSError) as exc:
            raise UpdateError(f"Архив обновления повреждён: {exc}") from exc

        roots = [p for p in (temp_dir / "src").iterdir() if p.is_dir()]
        if len(roots) != 1:
            raise UpdateError("Некорректная структура архива обновления.")

        incoming = roots[0]
        incoming_version = str(_read_json(incoming / "version.json").get("version", "0.0.0"))
        if incoming_version != status["latest"]:
            raise UpdateError("Версия архива не совпадает с опубликованной версией.")

        backed_up = _backup_existing(ROOT, backup_root)
        copied = 0

        for source in incoming.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(incoming)
            if _should_preserve(relative):
                continue
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1

    return {
        "ok": True,
        "updated": True,
        "current": status["current"],
        "latest": status["latest"],
        "restart_required": True,
        "files_copied": copied,
        "files_backed_up": backed_up,
        "backup": _safe_relative(backup_root),
        "repository": REPO,
        "components": status.get("components", []),
    }
