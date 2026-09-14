import os
import sqlite3
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from signalops.catalog import DatasetDefinition, load_catalog
from signalops.config import load_settings
from signalops.quality import QualityResult
from signalops.sync import SyncTarget, load_env_file, synchronize, target_is_due


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
    def test_quality_failure_keeps_previous_publication(self) -> None:
        source_definition = definition()
        source_definition = DatasetDefinition(
            key=source_definition.key,
            name=source_definition.name,
            adapter=source_definition.adapter,
            stream=source_definition.stream,
            entity_type=source_definition.entity_type,
            refresh_minutes=source_definition.refresh_minutes,
            source=source_definition.source,
            entities=({"key": "db:8000098", "city": "essen"},),
            quality=({"key": "valid_timestamp", "severity": "high"},),
            signals=source_definition.signals,
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config" / "base.toml"
            output = root / "site" / "data" / "summary.json"
            output.parent.mkdir(parents=True)
            output.write_text("previous publication", encoding="utf-8")
            settings = replace(load_settings(Path("config/base.toml")), data_dir=root / "data")
            with (
                patch("signalops.sync.load_settings", return_value=settings),
                patch(
                    "signalops.sync.load_catalog",
                    return_value={"db_changes": source_definition},
                ),
                patch("signalops.sync.target_is_due", return_value=(False, datetime.now(UTC))),
                patch(
                    "signalops.sync.assess",
                    return_value=[
                        QualityResult(
                            "valid_timestamp",
                            "failure",
                            1,
                            1,
                            {"severity": "high", "reason": "invalid"},
                        )
                    ],
                ),
            ):
                summary = synchronize(config, datasets=("db_changes",), cities=("essen",))

            self.assertEqual(summary.analysis_rows, 0)
            self.assertEqual(summary.quality_failures, ("essen/db_changes/valid_timestamp",))
            self.assertEqual(output.read_text(encoding="utf-8"), "previous publication")

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

    def test_weather_poll_is_due_every_six_hours(self) -> None:
        weather = load_catalog(Path("config/datasets"))["dwd_weather"]
        target = SyncTarget(weather, "essen", "Essen", "01303")
        checked = datetime(2026, 9, 14, 8, 40, tzinfo=UTC)
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
                VALUES ('dwd', '01303', 'observations', ?, 'success')
                """,
                (checked.isoformat(),),
            )
            due_early, _ = target_is_due(connection, target, checked + timedelta(minutes=359))
            due_on_time, _ = target_is_due(connection, target, checked + timedelta(minutes=360))
        self.assertFalse(due_early)
        self.assertTrue(due_on_time)


if __name__ == "__main__":
    unittest.main()
