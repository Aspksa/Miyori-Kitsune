from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import embeddings
import neural_runtime
import semantic_memory


class NeuralMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        semantic_memory.INDEX_FILE = Path(self.temp.name) / "vectors.json"
        os.environ.pop("MIYORI_EMBEDDING_MODEL", None)
        embeddings.reset_provider_cache()

    def tearDown(self):
        embeddings.reset_provider_cache()
        self.temp.cleanup()

    def test_hash_embedding_is_deterministic(self):
        provider = embeddings.get_provider()
        a = provider.encode("Miyori важная память")
        b = provider.encode("Miyori важная память")
        self.assertEqual(a, b)
        self.assertEqual(len(a), provider.dimensions)

    def test_semantic_index_returns_matching_item(self):
        items = [
            {"id": "one", "text": "Miyori хранит важную память", "updated_at": 1},
            {"id": "two", "text": "Погода и случайная заметка", "updated_at": 1},
        ]
        semantic_memory.sync(items)
        rows = semantic_memory.search("важная память Miyori", items, limit=2)
        self.assertEqual(rows[0]["id"], "one")

    def test_internal_runtime_remains_available(self):
        runtime = neural_runtime.runtime_for_model({
            "id": "miyori-internal-planner@0.1.0",
            "name": "miyori-internal-planner",
            "version": "0.1.0",
            "runtime": "internal",
        })
        self.assertTrue(runtime.available())

    def test_unknown_runtime_is_not_available(self):
        runtime = neural_runtime.runtime_for_model({
            "id": "unknown@1",
            "name": "unknown",
            "version": "1",
            "runtime": "unknown-runtime",
        })
        self.assertFalse(runtime.available())


if __name__ == "__main__":
    unittest.main()
