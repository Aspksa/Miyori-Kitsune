from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import teacher_gateway


class TeacherGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        teacher_gateway.FEEDBACK_FILE = Path(self.temp.name) / "feedback.json"
        self.old_status = teacher_gateway.foundation_status
        self.old_chat = teacher_gateway.foundation_chat

    def tearDown(self):
        teacher_gateway.foundation_status = self.old_status
        teacher_gateway.foundation_chat = self.old_chat
        self.temp.cleanup()

    def test_teacher_review_is_separate_training_signal(self):
        teacher_gateway.foundation_status = lambda: {
            "configured": True,
            "enabled": True,
            "auto_review": False,
            "model": "teacher-test",
        }
        teacher_gateway.foundation_chat = lambda *args, **kwargs: {
            "choices": [{
                "message": {
                    "content": '{"summary":"Хороший ответ","strengths":["ясно"],"issues":[],"corrections":[],"lessons":["сохранять ясность"],"recommended_answer":"Ответ Miyori","confidence":0.9,"tags":["quality"]}'
                }
            }],
            "usage": {"total_tokens": 42},
        }

        item = teacher_gateway.review(
            "Привет",
            "Ответ Miyori",
            context={"memory": {"items": []}},
            session_id="test",
        )
        self.assertEqual(item["teacher_model"], "teacher-test")
        self.assertFalse(item["accepted_for_training"])
        self.assertEqual(item["feedback"]["recommended_answer"], "Ответ Miyori")

        marked = teacher_gateway.mark_feedback(item["id"], True)
        self.assertTrue(marked["accepted_for_training"])
        self.assertTrue(marked["reviewed_by_user"])

    def test_auto_review_disabled_makes_no_paid_call(self):
        called = {"chat": 0}
        teacher_gateway.foundation_status = lambda: {
            "configured": True,
            "enabled": True,
            "auto_review": False,
            "model": "teacher-test",
        }
        def fake_chat(*args, **kwargs):
            called["chat"] += 1
            return {}
        teacher_gateway.foundation_chat = fake_chat

        result = teacher_gateway.review_if_enabled("a", "b")
        self.assertIsNone(result)
        self.assertEqual(called["chat"], 0)

    def test_teacher_never_marks_feedback_for_training_automatically(self):
        teacher_gateway.foundation_status = lambda: {
            "configured": True,
            "enabled": True,
            "auto_review": True,
            "model": "teacher-test",
        }
        teacher_gateway.foundation_chat = lambda *args, **kwargs: {
            "choices": [{"message": {"content": '{"summary":"ok","recommended_answer":"better"}'}}]
        }
        item = teacher_gateway.review_if_enabled("question", "answer")
        self.assertIsNotNone(item)
        self.assertFalse(item["accepted_for_training"])


if __name__ == "__main__":
    unittest.main()
