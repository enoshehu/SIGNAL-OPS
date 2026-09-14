from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from signalops.config import ConfigurationError, load_settings


class ConfigurationTests(unittest.TestCase):
    def test_loads_config_and_environment_overrides(self) -> None:
        environment = {
            **os.environ,
            "SIGNALOPS_ENV": "test",
            "SIGNALOPS_DATA_DIR": "tmp/test-data",
            "DB_API_CLIENT_ID": "client",
            "DB_API_KEY": "secret",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings(Path("config/base.toml"))

        self.assertEqual(settings.environment, "test")
        self.assertEqual(settings.data_dir.parts[-2:], ("tmp", "test-data"))
        self.assertEqual(settings.default_city, "essen")
        self.assertEqual(settings.dwd.station_id, "01303")
        self.assertEqual(settings.db.eva_number, "8000098")
        self.assertEqual(settings.city("duisburg").db_eva_number, "8000086")
        self.assertEqual(len(settings.cities), 4)
        self.assertTrue(settings.db.credentials_configured)

    def test_missing_config_has_clear_error(self) -> None:
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ConfigurationError, "Could not load configuration"):
                load_settings(Path(directory) / "missing.toml")
