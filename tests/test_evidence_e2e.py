import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.rebuild_evidence import rebuild
from signalops.analysis import hourly_summary
from signalops.publish import write_dashboard_json


class EvidenceEndToEndTests(unittest.TestCase):
    def test_committed_evidence_rebuilds_database_csv_and_dashboard(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "rebuild"
            observations, events, exported = rebuild(
                Path("evidence/raw"), output, Path("config/base.toml")
            )
            dashboard = Path(directory) / "summary.json"
            rows = hourly_summary(output / "signalops.sqlite")
            write_dashboard_json(rows, dashboard)
            payload = json.loads(dashboard.read_text(encoding="utf-8"))

        self.assertGreater(observations, 0)
        self.assertGreater(events, 0)
        self.assertEqual(exported, len(rows))
        self.assertEqual(payload["pairedHours"], sum(int(row["paired"]) for row in rows))
        self.assertEqual(len(payload["cities"]), 4)


if __name__ == "__main__":
    unittest.main()
