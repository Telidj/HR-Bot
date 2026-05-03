import tempfile
import unittest
from pathlib import Path

from services.document_reader import load_documents


class DocumentReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_context = tempfile.TemporaryDirectory(prefix=f"{self._testMethodName}-")
        self.temp_dir = Path(self.temp_context.name)
        (self.temp_dir / "nested").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_context.cleanup()

    def test_load_documents_uses_relative_source_path(self) -> None:
        doc_path = self.temp_dir / "nested" / "Payroll_FAQ.md"
        doc_path.write_text("Payroll happens twice per month.", encoding="utf-8")

        docs = load_documents(self.temp_dir)

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["source"], "nested/Payroll_FAQ.md")
        self.assertIn("Payroll happens twice per month.", docs[0]["text"])


if __name__ == "__main__":
    unittest.main()
