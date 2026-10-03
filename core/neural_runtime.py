from __future__ import annotations

import json
from pathlib import Path

from brain_runtime import BrainModelRuntime, InternalPlannerRuntime, ModelOutput
from model_registry import BUILTIN_MODEL_ID, active_model, list_models

ROOT = Path(__file__).resolve().parent.parent
MODELS_ROOT = (ROOT / "data" / "models").resolve()


class UnavailableNeuralRuntime:
    def __init__(self, model: dict, reason: str):
        self.model = model
        self.name = str(model.get("name") or "miyori-neural-unavailable")
        self.version = str(model.get("version") or "unknown")
        self.reason = reason

    def available(self) -> bool:
        return False

    def infer(self, message: str, context: dict, capabilities: dict) -> ModelOutput:
        return ModelOutput(
            text="",
            intent="delegate_to_brain_planner",
            actions=[],
            metadata={"runtime": self.name, "available": False, "reason": self.reason},
        )


class LlamaCppRuntime:
    """Local neural inference adapter for GGUF weights through optional llama-cpp-python."""

    def __init__(self, model: dict):
        self.model = model
        self.name = str(model.get("name") or "miyori-local-neural")
        self.version = str(model.get("version") or "unknown")
        self._llm = None
        self._error = None

    def _artifact(self) -> Path:
        raw = str(self.model.get("artifact_path") or "").strip()
        if not raw:
            raise ValueError("Model artifact_path is not configured.")
        path = Path(raw)
        if not path.is_absolute():
            path = (ROOT / raw).resolve()
        else:
            path = path.resolve()
        allowed_roots = [MODELS_ROOT, (ROOT / "data" / "brain" / "models").resolve()]
        if not any(root == path or root in path.parents for root in allowed_roots):
            raise PermissionError("Neural model artifact must be stored under data/models or data/brain/models.")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Neural model artifact not found: {path}")
        return path

    def _load(self):
        if self._llm is not None:
            return self._llm
        try:
            from llama_cpp import Llama
            metadata = self.model.get("metadata", {}) if isinstance(self.model.get("metadata"), dict) else {}
            self._llm = Llama(
                model_path=str(self._artifact()),
                n_ctx=max(1024, int(metadata.get("context_length", 4096) or 4096)),
                n_threads=metadata.get("threads"),
                verbose=False,
            )
            return self._llm
        except Exception as exc:
            self._error = str(exc)
            raise

    def available(self) -> bool:
        try:
            import llama_cpp  # noqa: F401
            self._artifact()
            return True
        except Exception as exc:
            self._error = str(exc)
            return False

    def _prompt(self, message: str, context: dict) -> str:
        memory_items = context.get("memory", {}).get("items", [])[:12]
        memory_text = "\n".join(f"- {item.get('text', '')}" for item in memory_items if item.get("text"))
        project = context.get("project")
        task = context.get("task")
        situational = {
            "project": project.get("name") if isinstance(project, dict) else None,
            "task": task.get("title") if isinstance(task, dict) else None,
            "memory_retrieval": context.get("memory", {}).get("retrieval"),
        }
        return (
            "Ты Miyori Kitsune, личная AI-система. Отвечай по-русски, точно и естественно. "
            "Не утверждай, что выполнила внешнее действие, если Action Gateway его не выполнил.\n"
            f"Состояние: {json.dumps(situational, ensure_ascii=False)}\n"
            f"Релевантная память:\n{memory_text or '- нет'}\n\n"
            f"Пользователь: {message}\nMiyori:"
        )

    def infer(self, message: str, context: dict, capabilities: dict) -> ModelOutput:
        try:
            llm = self._load()
            metadata = self.model.get("metadata", {}) if isinstance(self.model.get("metadata"), dict) else {}
            result = llm(
                self._prompt(message, context),
                max_tokens=max(64, min(int(metadata.get("max_tokens", 512) or 512), 2048)),
                temperature=float(metadata.get("temperature", 0.7) or 0.7),
                stop=["\nПользователь:", "\nUser:"],
            )
            text = str(result.get("choices", [{}])[0].get("text", "")).strip()
            return ModelOutput(
                text=text,
                intent="conversation",
                actions=[],
                metadata={
                    "runtime": "llama_cpp",
                    "model_id": self.model.get("id"),
                    "neural": True,
                    "available": True,
                },
            )
        except Exception as exc:
            self._error = str(exc)
            return ModelOutput(
                text="",
                intent="delegate_to_brain_planner",
                actions=[],
                metadata={
                    "runtime": "llama_cpp",
                    "model_id": self.model.get("id"),
                    "neural": True,
                    "available": False,
                    "error": self._error,
                },
            )


def runtime_for_model(model: dict) -> BrainModelRuntime:
    runtime = str(model.get("runtime") or "internal")
    if runtime == "internal" or model.get("id") == BUILTIN_MODEL_ID:
        return InternalPlannerRuntime()
    if runtime == "llama_cpp":
        return LlamaCppRuntime(model)
    return UnavailableNeuralRuntime(model, f"Unsupported runtime: {runtime}")


def active_runtime() -> BrainModelRuntime:
    return runtime_for_model(active_model())


def runtime_status() -> dict:
    model = active_model()
    runtime = runtime_for_model(model)
    available = runtime.available()
    return {
        "model_id": model.get("id"),
        "runtime": model.get("runtime"),
        "name": getattr(runtime, "name", model.get("name")),
        "version": getattr(runtime, "version", model.get("version")),
        "available": bool(available),
        "neural": model.get("runtime") not in {None, "internal"},
        "fallback": "miyori-internal-planner" if not available and model.get("runtime") != "internal" else None,
    }
