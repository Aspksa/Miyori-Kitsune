from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import embodiment
import embeddings
import memory
import model_registry
import semantic_memory
import self_development


class CognitiveFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        memory.MEMORY_FILE = base / "memory.json"
        semantic_memory.INDEX_FILE = base / "memory-vectors.json"
        embeddings.reset_provider_cache()
        model_registry.REGISTRY_FILE = base / "models" / "registry.json"
        embodiment.STATE_FILE = base / "embodiment.json"
        self_development.PROPOSALS_FILE = base / "self-development" / "proposals.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_relevance_memory_prefers_matching_context(self):
        expected = memory.add_memory("remember", "Miyori должна сохранять важный контекст", importance=0.9)
        memory.add_memory("remember", "Совсем другая запись", importance=0.2)
        rows = memory.retrieve_relevant("важный контекст")
        self.assertEqual(rows[0]["id"], expected["id"])

    def test_model_activation_requires_explicit_approval(self):
        item = model_registry.register_model("miyori-test@0.1", "miyori-test", "0.1")
        model_registry.transition(item["id"], "testing")
        model_registry.transition(item["id"], "approved")
        with self.assertRaises(PermissionError):
            model_registry.transition(item["id"], "active")
        model_registry.transition(item["id"], "active", approved=True)
        self.assertEqual(model_registry.active_model()["id"], item["id"])

    def test_embodiment_records_only_enabled_sensor_observations(self):
        result = embodiment.record_observation("vision", "test frame", source="unit-test")
        self.assertEqual(result["channel"], "vision")
        with self.assertRaises(PermissionError):
            embodiment.record_observation("hearing", "test audio", source="unit-test")

    def test_self_development_cannot_skip_lifecycle(self):
        proposal = self_development.propose("Test", "Reason", "core/brain.py", "high")
        with self.assertRaises(ValueError):
            self_development.transition(proposal["id"], "approved", approved=True)

        self_development.transition(proposal["id"], "sandboxed")
        self_development.record_test(proposal["id"], "unit", True)
        self_development.transition(proposal["id"], "tested")
        self_development.transition(proposal["id"], "approved", approved=True)

        with self.assertRaises(PermissionError):
            self_development.transition(proposal["id"], "applied")


if __name__ == "__main__":
    unittest.main()
