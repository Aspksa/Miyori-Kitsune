from __future__ import annotations

import json
import shutil
import tempfile
import threading
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
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "update-history.json"
INSTALL_STATE_FILE = DATA_DIR / "install-state.json"
MOBILE_DOWNLOAD_DIR = ROOT / "mobile" / "downloads"
PRESERVE_TOP_LEVEL = {".git", "data", "logs", "backups", "mobile"}
PRESERVE_FILES = {"config/local.json"}

RAW_VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.json"
ZIP_URL = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"
COMMIT_URL = f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"

_UPDATE_LOCK = threading.Lock()
_UPDATE_STATE = {
    "running": False,
    "stage": "idle",
    "progress": 0,
    "downloaded": 0,
    "total": 0,
    "message": "",
    "error": None,
    "result": None,
}


class UpdateError(RuntimeError):
    pass


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for part in str(value).split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def _version_gte(actual: str, required: str) -> bool:
    a, b = _version_tuple(actual), _version_tuple(required)
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) >= b + (0,) * (width - len(b))


def _git_head() -> str:
    git = ROOT / ".git"
    if not git.exists():
        return ""
    head = git / "HEAD"
    try:
        value = head.read_text(encoding="utf-8").strip()
        if value.startswith("ref: "):
            ref = value[5:]
            ref_file = git / ref
            if ref_file.exists():
                return ref_file.read_text(encoding="utf-8").strip()
            packed = git / "packed-refs"
            if packed.exists():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line and not line.startswith("#") and line.endswith(" " + ref):
                        return line.split(" ", 1)[0]
            return ""
        return value
    except OSError:
        return ""


def local_build() -> str:
    state = _read_json(INSTALL_STATE_FILE)
    return str(state.get("build") or _git_head() or "local")


def local_manifest() -> dict:
    data = _read_json(VERSION_FILE)
    return {
        "version": str(data.get("version", "0.0.0")),
        "channel": str(data.get("channel", "stable")),
        "repository": str(data.get("repository", REPO)),
        "components": {str(k): str(v) for k, v in data.get("components", {}).items()},
        "dependencies": data.get("dependencies", {}),
        "mobile_client": data.get("mobile_client", {}),
        "changes": data.get("changes", []),
        "build": local_build(),
    }


def local_version() -> str:
    return local_manifest()["version"]


def _request(url: str, timeout: int = 15, method: str = "GET"):
    return urllib.request.urlopen(
        urllib.request.Request(
            url,
            method=method,
            headers={
                "User-Agent": "Miyori-Kitsune-Updater",
                "Accept": "application/vnd.github+json, application/json",
                "Cache-Control": "no-cache",
            },
        ),
        timeout=timeout,
    )


def _fetch_json(url: str, timeout: int = 12) -> dict:
    try:
        with _request(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise UpdateError(f"Не удалось получить данные обновления: {exc}") from exc


def _remote_commit() -> str:
    try:
        return str(_fetch_json(COMMIT_URL, timeout=12).get("sha", ""))
    except UpdateError:
        return ""


def _remote_size() -> int:
    try:
        with _request(ZIP_URL, timeout=12, method="HEAD") as response:
            return int(response.headers.get("Content-Length") or 0)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0


def _validate_dependencies(manifest: dict) -> list[dict]:
    components = {str(k): str(v) for k, v in manifest.get("components", {}).items()}
    issues = []
    for component, requirements in manifest.get("dependencies", {}).items():
        for dependency, minimum in requirements.items():
            actual = components.get(dependency, "0.0.0")
            if not _version_gte(actual, str(minimum)):
                issues.append({
                    "component": component,
                    "dependency": dependency,
                    "required": str(minimum),
                    "actual": actual,
                })
    return issues


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

    dependency_issues = _validate_dependencies(remote)
    remote_build = _remote_commit()

    return {
        "ok": True,
        "current": current,
        "latest": latest,
        "current_build": local.get("build", "local"),
        "latest_build": remote_build or "unknown",
        "available": latest != current or any(item["changed"] for item in component_changes),
        "channel": str(remote.get("channel", "stable")),
        "repository": REPO,
        "components": component_changes,
        "dependencies_ok": not dependency_issues,
        "dependency_issues": dependency_issues,
        "size": _remote_size(),
        "changes": remote.get("changes", []),
        "mobile_client": remote.get("mobile_client", {}),
    }


def mobile_update_status() -> dict:
    remote = _fetch_json(RAW_VERSION_URL)
    local = local_manifest()
    remote_mobile = remote.get("mobile_client", {})
    local_mobile = local.get("mobile_client", {})
    current = str(local_mobile.get("version", local.get("components", {}).get("mobile", "0.0.0")))
    latest = str(remote_mobile.get("version", current))
    min_core = str(remote_mobile.get("min_core", "0.0.0"))
    compatible = _version_gte(local["components"].get("core", "0.0.0"), min_core)
    return {
        "ok": True,
        "current": current,
        "latest": latest,
        "available": latest != current,
        "compatible": compatible,
        "min_core": min_core,
        "platform": str(remote_mobile.get("platform", "android")),
        "download_url": str(remote_mobile.get("download_url", "")),
        "download_ready": bool(remote_mobile.get("download_url")),
        "notes": str(remote_mobile.get("notes", "")),
    }


def update_history(limit: int = 30) -> list[dict]:
    data = _read_json(HISTORY_FILE, [])
    if not isinstance(data, list):
        return []
    return list(reversed(data[-limit:]))


def _append_history(entry: dict) -> None:
    history = _read_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        history = []
    history.append(entry)
    _write_json(HISTORY_FILE, history[-100:])


def _set_state(**changes) -> None:
    with _UPDATE_LOCK:
        _UPDATE_STATE.update(changes)


def update_progress() -> dict:
    with _UPDATE_LOCK:
        return dict(_UPDATE_STATE)


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


def _download_zip(archive: Path, expected_total: int) -> tuple[int, int]:
    downloaded = 0
    _set_state(stage="download", progress=0, downloaded=0, total=expected_total, message="Загрузка пакета обновления…")
    try:
        with _request(ZIP_URL, timeout=60) as response, archive.open("wb") as out:
            total = int(response.headers.get("Content-Length") or expected_total or 0)
            _set_state(total=total)
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                progress = int(downloaded * 100 / total) if total else 0
                _set_state(downloaded=downloaded, total=total, progress=min(progress, 99))
        return downloaded, total
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"Не удалось скачать обновление: {exc}") from exc


def _perform_update() -> dict:
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    status = check_update()

    if not status["dependencies_ok"]:
        raise UpdateError("Обновление заблокировано: не выполнены зависимости компонентов.")
    if not status["available"]:
        return {**status, "updated": False, "restart_required": False}

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_root = BACKUP_DIR / stamp

    with tempfile.TemporaryDirectory(prefix="miyori-update-") as temp:
        temp_dir = Path(temp)
        archive = temp_dir / "update.zip"
        downloaded, total = _download_zip(archive, status.get("size", 0))

        _set_state(stage="extract", progress=99, message="Распаковка и проверка пакета…")
        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(temp_dir / "src")
        except (zipfile.BadZipFile, OSError) as exc:
            raise UpdateError(f"Архив обновления повреждён: {exc}") from exc

        roots = [p for p in (temp_dir / "src").iterdir() if p.is_dir()]
        if len(roots) != 1:
            raise UpdateError("Некорректная структура архива обновления.")

        incoming = roots[0]
        incoming_manifest = _read_json(incoming / "version.json")
        incoming_version = str(incoming_manifest.get("version", "0.0.0"))
        if incoming_version != status["latest"]:
            raise UpdateError("Версия архива не совпадает с опубликованной версией.")
        issues = _validate_dependencies(incoming_manifest)
        if issues:
            raise UpdateError("Пакет содержит несовместимые зависимости компонентов.")

        _set_state(stage="backup", message="Создание резервной копии…")
        backed_up = _backup_existing(ROOT, backup_root)

        _set_state(stage="install", message="Установка файлов…")
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

    build = status.get("latest_build") or ""
    _write_json(INSTALL_STATE_FILE, {
        "version": status["latest"],
        "build": build,
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

    changed = [x["name"] for x in status.get("components", []) if x.get("changed")]
    result = {
        "ok": True,
        "updated": True,
        "current": status["current"],
        "latest": status["latest"],
        "build": build,
        "restart_required": True,
        "files_copied": copied,
        "files_backed_up": backed_up,
        "downloaded": downloaded,
        "size": total or downloaded,
        "backup": _safe_relative(backup_root),
        "repository": REPO,
        "components": status.get("components", []),
        "changes": status.get("changes", []),
    }
    _append_history({
        "version": status["latest"],
        "build": build,
        "date": started,
        "modules": changed,
        "changes": status.get("changes", []),
        "size": total or downloaded,
        "result": "success",
    })
    return result


def _update_worker() -> None:
    try:
        result = _perform_update()
        _set_state(running=False, stage="done", progress=100, message="Обновление завершено.", result=result, error=None)
    except Exception as exc:
        _append_history({
            "version": local_version(),
            "build": local_build(),
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "modules": [],
            "changes": [],
            "size": update_progress().get("downloaded", 0),
            "result": "failed",
            "error": str(exc),
        })
        _set_state(running=False, stage="error", message=str(exc), error=str(exc), result=None)


def start_update() -> dict:
    with _UPDATE_LOCK:
        if _UPDATE_STATE["running"]:
            return dict(_UPDATE_STATE)
        _UPDATE_STATE.update({
            "running": True,
            "stage": "starting",
            "progress": 0,
            "downloaded": 0,
            "total": 0,
            "message": "Подготовка обновления…",
            "error": None,
            "result": None,
        })
    threading.Thread(target=_update_worker, daemon=True).start()
    return update_progress()


def download_mobile_client() -> dict:
    status = mobile_update_status()
    if not status["compatible"]:
        raise UpdateError(f"Мобильный клиент требует Core >= {status['min_core']}.")
    if not status["download_ready"]:
        raise UpdateError("Пакет мобильного клиента ещё не опубликован в GitHub Releases.")

    MOBILE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(status["download_url"]).suffix or ".apk"
    target = MOBILE_DOWNLOAD_DIR / f"MiyoriKitsune-Mobile-{status['latest']}{suffix}"
    try:
        with _request(status["download_url"], timeout=120) as response, target.open("wb") as out:
            shutil.copyfileobj(response, out)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"Не удалось скачать мобильный клиент: {exc}") from exc

    return {"ok": True, "downloaded": True, "path": _safe_relative(target), **status}
