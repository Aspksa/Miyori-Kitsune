from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import cloudru
import model_registry
import neural_runtime
import student_gateway


class CloudStudentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        model_registry.REGISTRY_FILE = Path(self.temp.name) / "models" / "registry.json"
        self.old_student_status = student_gateway.cloud_student_status
        self.old_runtime_status = neural_runtime.cloud_student_status
        self.cloud = {
            "configured": True,
            "enabled": True,
            "endpoint": "https://student.modelrun.inference.cloud.ru/v1",
            "model": "Qwen/Qwen3-8B",
            "version": "0.1.0",
            "api_key_saved": True,
            "provider": "cloudru-ml-inference",
            "role": "miyori-student",
        }
        student_gateway.cloud_student_status = lambda: dict(self.cloud)
        neural_runtime.cloud_student_status = lambda: dict(self.cloud)

    def tearDown(self):
        student_gateway.cloud_student_status = self.old_student_status
        neural_runtime.cloud_student_status = self.old_runtime_status
        self.temp.cleanup()

    def test_cloudru_student_endpoint_is_restricted(self):
        self.assertEqual(
            cloudru._normalize_student_endpoint("https://abc.modelrun.inference.cloud.ru"),
            "https://abc.modelrun.inference.cloud.ru/v1",
        )
        self.assertEqual(
            cloudru._normalize_student_endpoint("https://abc.modelrun.inference.cloud.ru/v1/chat/completions"),
            "https://abc.modelrun.inference.cloud.ru/v1",
        )
        with self.assertRaises(ValueError):
            cloudru._normalize_student_endpoint("https://example.com/v1")

    def test_student_registers_as_candidate(self):
        item = student_gateway.register_current()
        self.assertEqual(item["runtime"], "cloud_ml_inference")
        self.assertEqual(item["stage"], "candidate")
        self.assertEqual(item["metadata"]["role"], "miyori-student")
        self.assertFalse(item["metadata"]["teacher"])

    def test_student_requires_evaluation_and_explicit_promotion(self):
        item = student_gateway.register_current()
        item = student_gateway.prepare_for_evaluation()
        self.assertEqual(item["stage"], "testing")

        with self.assertRaises(ValueError):
            student_gateway.promote_current(approved=True)

        model_registry.update_metrics(item["id"], {"evaluation_score": 1.0})
        with self.assertRaises(PermissionError):
            student_gateway.promote_current(approved=False)

        active = student_gateway.promote_current(approved=True)
        self.assertEqual(active["stage"], "active")
        self.assertEqual(model_registry.active_model()["id"], item["id"])

    def test_active_student_cannot_be_silently_reconfigured(self):
        item = student_gateway.register_current()
        student_gateway.prepare_for_evaluation()
        model_registry.update_metrics(item["id"], {"evaluation_score": 1.0})
        student_gateway.promote_current(approved=True)

        with self.assertRaises(ValueError):
            student_gateway.validate_configuration_change({
                "student_version": "0.1.0",
                "student_endpoint": "https://other.modelrun.inference.cloud.ru/v1",
                "student_model": "Qwen/Qwen3-8B",
            })

        student_gateway.validate_configuration_change({
            "student_version": "0.2.0",
            "student_endpoint": "https://other.modelrun.inference.cloud.ru/v1",
            "student_model": "Qwen/Qwen3-8B",
        })

    def test_student_rollback_requires_approval(self):
        item = student_gateway.register_current()
        student_gateway.prepare_for_evaluation()
        model_registry.update_metrics(item["id"], {"evaluation_score": 1.0})
        student_gateway.promote_current(approved=True)

        with self.assertRaises(PermissionError):
            student_gateway.rollback_current(approved=False)

        restored = student_gateway.rollback_current(approved=True)
        self.assertEqual(restored["id"], model_registry.BUILTIN_MODEL_ID)
        self.assertEqual(model_registry.active_model()["id"], model_registry.BUILTIN_MODEL_ID)

    def test_runtime_refuses_registry_configuration_mismatch(self):
        item = student_gateway.register_current()
        runtime = neural_runtime.CloudStudentRuntime(item)
        self.assertTrue(runtime.available())

        self.cloud["endpoint"] = "https://other.modelrun.inference.cloud.ru/v1"
        self.assertFalse(runtime.available())


if __name__ == "__main__":
    unittest.main()
