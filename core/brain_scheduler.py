from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from sleep_engine import consolidate

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "data" / "brain" / "sleep-state.json"
_INTERVAL_SECONDS = 1800
_STOP = threading.Event()

def _write(data):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATE_FILE)

def run_once():
    result = consolidate()
    _write({"last_run": int(time.time()), "result": result})
    return result

def _worker():
    while not _STOP.wait(_INTERVAL_SECONDS):
        try:
            run_once()
        except Exception as exc:
            _write({"last_run": int(time.time()), "error": str(exc)})

def start():
    thread = threading.Thread(target=_worker, name="MiyoriSleepEngine", daemon=True)
    thread.start()
    return thread

def stop():
    _STOP.set()
