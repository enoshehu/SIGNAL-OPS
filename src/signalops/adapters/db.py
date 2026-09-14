"""Deutsche Bahn Timetables plan download and small XML parser."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from signalops.config import DBSettings
from signalops.domain import RawArtifact, RawRecord
from signalops.http import HttpClient


class DeutscheBahnTimetablesAdapter:
    name = "db"

    def __init__(
        self,
        settings: DBSettings,
        http: HttpClient | None = None,
        requested_at: datetime | None = None,
    ) -> None:
        self.settings = settings
        self.http = http or HttpClient()
        self.requested_at = requested_at or datetime.now(ZoneInfo("Europe/Berlin"))

    @property
    def url(self) -> str:
        date = self.requested_at.strftime("%y%m%d")
        hour = self.requested_at.strftime("%H")
        return f"{self.settings.base_url}/plan/{self.settings.eva_number}/{date}/{hour}"

    @property
    def ready(self) -> bool:
        return self.settings.enabled and self.settings.credentials_configured

    def download(self) -> RawArtifact:
        if not self.settings.credentials_configured:
            raise RuntimeError("Set DB_API_CLIENT_ID and DB_API_KEY before DB ingestion")
        result = self.http.get(
            self.url,
            headers={
                "DB-Client-Id": self.settings.client_id or "",
                "DB-Api-Key": self.settings.api_key or "",
            },
            timeout=self.settings.timeout_seconds,
        )
        return RawArtifact(
            source=self.name,
            external_id=f"plan-{self.settings.eva_number}-{self.requested_at:%y%m%d%H}",
            filename=f"plan_{self.settings.eva_number}_{self.requested_at:%y%m%d_%H}.xml",
            retrieved_at=result.retrieved_at,
            content=result.content,
            content_type=result.content_type,
            provenance={"source_url": result.url, "station_eva": self.settings.eva_number},
        )

    def parse(self, artifact: RawArtifact) -> Iterable[RawRecord]:
        try:
            root = ElementTree.fromstring(artifact.content)
        except ElementTree.ParseError as exc:
            raise ValueError("DB response is not valid XML") from exc
        for stop in root.findall(".//s"):
            stop_id = stop.attrib.get("id")
            if not stop_id:
                continue
            yield RawRecord(
                source=self.name,
                external_id=stop_id,
                retrieved_at=artifact.retrieved_at,
                payload={
                    "station_eva": self.settings.eva_number,
                    "stop_id": stop_id,
                    "raw_xml": ElementTree.tostring(stop, encoding="unicode"),
                },
                provenance={"source_url": artifact.provenance["source_url"]},
            )
