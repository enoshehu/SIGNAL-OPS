import os
import sqlite3
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from signalops.catalog import DatasetDefinition
from signalops.sync import SyncTarget, load_env_file, target_is_due


def definition(refresh_minutes: int = 15) -> DatasetDefinition:
    return DatasetDefinition(
        key="db_changes",
        name="DB changes",
        adapter="db",
        stream="changes",
        entity_type="rail_station",
        refresh_minutes=refresh_minutes,
        source={},
        entities=(),
        quality=(),
        signals=(),
    )


class SyncTests(unittest.TestCase):
    def test_literal_env_loader_does_not_execute_shell_syntax(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("SAFE='literal $(touch never)'\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                loaded = load_env_file(path)
                self.assertEqual(loaded, ("SAFE",))
                self.assertEqual(os.environ["SAFE"], "literal $(touch never)")
            self.assertFalse((Path(directory) / "never").exists())

    def test_target_without_history_is_due(self) -> None:
        target = SyncTarget(definition(), "essen", "Essen", "8000098")
        with sqlite3.connect(":memory:") as connection:
            connection.execute(
                """
                CREATE TABLE artifact_imports (
                  source TEXT, scope_key TEXT, stream_key TEXT, loaded_at TEXT
                )
                """
            )
            due, last = target_is_due(connection, target, datetime(2026, 9, 14, tzinfo=UTC))
        self.assertTrue(due)
        self.assertIsNone(last)

    def test_success_clock_controls_refresh_interval(self) -> None:
        target = SyncTarget(definition(), "essen", "Essen", "8000098")
        checked = datetime(2026, 9, 14, 10, tzinfo=UTC)
        with sqlite3.connect(":memory:") as connection:
            connection.execute(
                """
                CREATE TABLE artifact_imports (
                  source TEXT, scope_key TEXT, stream_key TEXT, loaded_at TEXT
                )
                """
            )
            target_is_due(connection, target, checked)
            connection.execute(
                """
                INSERT INTO collection_runs
                  (source, scope_key, stream_key, checked_at, status)
                VALUES ('db', '8000098', 'changes', ?, 'success')
                """,
                (checked.isoformat(),),
            )
            due_early, _ = target_is_due(connection, target, checked + timedelta(minutes=14))
            due_on_time, _ = target_is_due(connection, target, checked + timedelta(minutes=15))
        self.assertFalse(due_early)
        self.assertTrue(due_on_time)


if __name__ == "__main__":
    unittest.main()
