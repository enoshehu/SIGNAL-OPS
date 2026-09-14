import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.failure_drill import run_drill


class FailureDrillTests(unittest.TestCase):
    def test_corrupt_source_is_contained_and_recovery_is_imported(self) -> None:
        with TemporaryDirectory() as directory:
            report = Path(directory) / "drill.md"
            run_drill(report)
            text = report.read_text(encoding="utf-8")
        self.assertIn("Detection: **PASS**", text)
        self.assertIn("Recovery: **PASS**", text)
        self.assertIn("inserted 1 record", text)


if __name__ == "__main__":
    unittest.main()
