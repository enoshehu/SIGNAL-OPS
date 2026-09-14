from datetime import UTC, datetime
from io import BytesIO
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from signalops.adapters import DeutscheBahnTimetablesAdapter, DWDOpenDataAdapter
from signalops.config import DBSettings, DWDSettings
from signalops.domain import RawArtifact
from signalops.http import Download


class FakeHttpClient:
    def __init__(self, content: bytes, content_type: str) -> None:
        self.content = content
        self.content_type = content_type
        self.calls: list[tuple[str, dict[str, str], int]] = []

    def get(self, url: str, *, headers: dict[str, str], timeout: int) -> Download:
        self.calls.append((url, headers, timeout))
        return Download(url, self.content, self.content_type, datetime(2026, 9, 14, tzinfo=UTC))


def dwd_zip() -> bytes:
    content = BytesIO()
    with ZipFile(content, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "produkt_tu_stunde_sample_00433.txt",
            "STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU;eor\r\n"
            "433;2026091409;3;18.2;71.0;eor\r\n"
            "433;2026091410;3;-999;70.0;eor\r\n",
        )
    return content.getvalue()


class AdapterTests(unittest.TestCase):
    def test_dwd_public_adapter_is_ready_without_credentials(self) -> None:
        settings = DWDSettings(
            True,
            "https://opendata.dwd.de/climate_environment/CDC",
            30,
            "00433",
            "recent/stundenwerte_TU_{station_id}_akt.zip",
        )
        http = FakeHttpClient(dwd_zip(), "application/zip")
        adapter = DWDOpenDataAdapter(settings, http=http)

        artifact = adapter.download()
        records = list(adapter.parse(artifact))

        self.assertTrue(adapter.ready)
        self.assertIn("stundenwerte_TU_00433_akt.zip", adapter.url)
        self.assertEqual(records[0].payload["temperature_c"], 18.2)
        self.assertIsNone(records[1].payload["temperature_c"])

    def test_db_adapter_requires_external_credentials(self) -> None:
        settings = DBSettings(True, "https://example.invalid", 30, "8011160", None, None)
        adapter = DeutscheBahnTimetablesAdapter(settings)
        self.assertFalse(adapter.ready)
        with self.assertRaisesRegex(RuntimeError, "DB_API_CLIENT_ID"):
            adapter.download()

    def test_db_adapter_sends_secret_headers_and_parses_xml(self) -> None:
        xml = b'<timetable station="Berlin Hbf"><s id="stop-1"><dp pt="2609141000"/></s></timetable>'
        http = FakeHttpClient(xml, "application/xml")
        settings = DBSettings(True, "https://db.example/v1", 30, "8011160", "client", "key")
        adapter = DeutscheBahnTimetablesAdapter(
            settings,
            http=http,
            requested_at=datetime(2026, 9, 14, 10, tzinfo=UTC),
        )

        artifact = adapter.download()
        records = list(adapter.parse(artifact))

        self.assertEqual(adapter.url, "https://db.example/v1/plan/8011160/260914/10")
        self.assertEqual(http.calls[0][1], {"DB-Client-Id": "client", "DB-Api-Key": "key"})
        self.assertEqual(records[0].external_id, "stop-1")

    def test_dwd_parser_reports_missing_columns(self) -> None:
        content = BytesIO()
        with ZipFile(content, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "produkt_tu_stunde_sample_00433.txt",
                "STATIONS_ID;MESS_DATUM;TT_TU\r\n433;2026091410;18.2\r\n",
            )
        settings = DWDSettings(
            True, "https://example.invalid", 30, "00433", "weather_{station_id}.zip"
        )
        adapter = DWDOpenDataAdapter(settings)
        artifact = RawArtifact(
            "dwd",
            "sample",
            "weather.zip",
            datetime(2026, 9, 14, tzinfo=UTC),
            content.getvalue(),
            "application/zip",
            {"source_url": "https://example.invalid/weather.zip"},
        )

        with self.assertRaisesRegex(ValueError, "missing columns"):
            list(adapter.parse(artifact))
