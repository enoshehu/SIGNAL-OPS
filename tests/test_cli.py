from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from signalops.cli import main
from signalops.config import load_settings


class CliTests(unittest.TestCase):
    def test_dry_run_makes_no_request_and_writes_nothing(self) -> None:
        output = StringIO()
        with TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"SIGNALOPS_DATA_DIR": directory}, clear=False):
                with redirect_stdout(output):
                    result = main(
                        [
                            "ingest",
                            "--source",
                            "dwd",
                            "--config",
                            "config/base.toml",
                            "--dry-run",
                        ]
                    )

            self.assertEqual(result, 0)
            self.assertFalse((Path(directory) / "raw").exists())
            self.assertIn("no request sent and no file written", output.getvalue())

    def test_db_dry_run_does_not_print_credentials(self) -> None:
        output = StringIO()
        environment = {"DB_API_CLIENT_ID": "hidden-client", "DB_API_KEY": "hidden-key"}
        with patch.dict("os.environ", environment, clear=False):
            with redirect_stdout(output):
                result = main(
                    [
                        "ingest",
                        "--source",
                        "db",
                        "--config",
                        "config/base.toml",
                        "--at",
                        "2026-09-14T10:00:00+00:00",
                        "--dry-run",
                    ]
                )

        self.assertEqual(result, 0)
        self.assertNotIn("hidden-client", output.getvalue())
        self.assertNotIn("hidden-key", output.getvalue())
        self.assertIn("/plan/8000098/260914/10", output.getvalue())

    def test_city_selects_its_db_station(self) -> None:
        output = StringIO()
        environment = {"DB_API_CLIENT_ID": "client", "DB_API_KEY": "key"}
        with patch.dict("os.environ", environment, clear=False), redirect_stdout(output):
            result = main(
                [
                    "ingest", "--source", "db", "--city", "koeln",
                    "--at", "2026-09-14T10:00:00+02:00", "--dry-run",
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("city: Köln", output.getvalue())
        self.assertIn("/plan/8000207/260914/10", output.getvalue())

    def test_db_changes_dry_run_uses_full_changes_endpoint(self) -> None:
        output = StringIO()
        environment = {"DB_API_CLIENT_ID": "client", "DB_API_KEY": "key"}
        with patch.dict("os.environ", environment, clear=False), redirect_stdout(output):
            result = main([
                "ingest", "--source", "db", "--city", "essen",
                "--db-feed", "changes", "--dry-run",
            ])
        self.assertEqual(result, 0)
        self.assertIn("/fchg/8000098", output.getvalue())

    def test_unknown_city_has_clear_error(self) -> None:
        with redirect_stdout(StringIO()):
            result = main(["ingest", "--source", "dwd", "--city", "berlin", "--dry-run"])
        self.assertEqual(result, 2)

    def test_rejects_invalid_or_naive_db_time(self) -> None:
        for value in ("not-a-date", "2026-09-14T10:00:00"):
            with self.subTest(value=value):
                with redirect_stdout(StringIO()):
                    result = main(
                        [
                            "ingest",
                            "--source",
                            "db",
                            "--config",
                            "config/base.toml",
                            "--at",
                            value,
                            "--dry-run",
                        ]
                    )
                self.assertEqual(result, 2)

    def test_disabled_source_cannot_run(self) -> None:
        settings = load_settings("config/base.toml")
        disabled = replace(settings, dwd=replace(settings.dwd, enabled=False))
        output = StringIO()
        with patch("signalops.cli.load_settings", return_value=disabled):
            with redirect_stdout(output):
                result = main(
                    [
                        "ingest",
                        "--source",
                        "dwd",
                        "--config",
                        "config/base.toml",
                        "--dry-run",
                    ]
                )

        self.assertEqual(result, 2)
        self.assertIn("disabled", output.getvalue())
