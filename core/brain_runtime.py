from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ModelOutput:
    text: str
    intent: str = "conversation"
    actions: list[dict] | None = None
    metadata: dict | None = None


class BrainModelRuntime(Protocol):
    name: str
    version: str

    def available(self) -> bool:
        ...

    def infer(self, message: str, context: dict, capabilities: dict) -> ModelOutput:
        ...


class InternalPlannerRuntime:
    """Built-in Miyori runtime used before a trained neural model is attached."""

    name = "miyori-internal-planner"
    version = "0.1.0"

    def available(self) -> bool:
        return True

    def infer(self, message: str, context: dict, capabilities: dict) -> ModelOutput:
        return ModelOutput(
            text="",
            intent="delegate_to_brain_planner",
            actions=[],
            metadata={
                "runtime": self.name,
                "context_items": context.get("summary", {}),
                "capability_count": len(capabilities.get("actions", [])),
            },
        )
