import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "docs" / "quality_check_questions.json"
DOCUMENTS_DIR = PROJECT_ROOT / "documents"


class QualityCheckDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        with DATASET_PATH.open("r", encoding="utf-8") as handle:
            self.dataset = json.load(handle)
        self.items = self.dataset["items"]

    def test_dataset_has_expected_size_and_unique_ids(self) -> None:
        ids = [item["id"] for item in self.items]

        self.assertEqual(len(self.items), 30)
        self.assertEqual(len(ids), len(set(ids)))

    def test_dataset_covers_required_topics(self) -> None:
        topics = {item["topic"] for item in self.items}

        self.assertEqual(
            topics,
            {"PTO", "Payroll", "Benefits", "IT support", "Onboarding"},
        )

    def test_expected_documents_exist(self) -> None:
        for item in self.items:
            for source in item["expected_source_documents"]:
                self.assertTrue(
                    (DOCUMENTS_DIR / source).exists(),
                    f"{item['id']} references missing source document {source}",
                )

    def test_behavior_flags_are_consistent(self) -> None:
        behavior_to_flag = {
            "answer": "should_answer",
            "clarify": "should_ask_clarification",
            "refuse": "should_refuse",
            "create_request": "should_create_request",
        }
        valid_behaviors = set(behavior_to_flag)

        for item in self.items:
            behavior = item["expected_behavior"]
            self.assertIn(behavior, valid_behaviors, item["id"])
            true_flags = [
                flag
                for flag in behavior_to_flag.values()
                if bool(item.get(flag, False))
            ]
            self.assertEqual(true_flags, [behavior_to_flag[behavior]], item["id"])
            if behavior == "create_request":
                self.assertTrue(item["expected_request_type"], item["id"])
                self.assertEqual(item["expected_source_documents"], [], item["id"])


if __name__ == "__main__":
    unittest.main()
