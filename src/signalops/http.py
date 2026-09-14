"""Small standard-library HTTP client used by source adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import time
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DownloadError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Download:
    url: str
    content: bytes
    content_type: str
    retrieved_at: datetime


class HttpClient:
    def __init__(
        self,
        opener: Callable[..., object] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
        max_bytes: int = 5_000_000,
    ) -> None:
        self.opener = opener
        self.sleeper = sleeper
        self.max_bytes = max_bytes

    def get(self, url: str, *, headers: Mapping[str, str], timeout: int) -> Download:
        request = Request(url, headers={**headers, "User-Agent": "signalops/0.2"})
        for attempt in range(2):
            try:
                with self.opener(request, timeout=timeout) as response:
                    content = response.read(self.max_bytes + 1)
                    if len(content) > self.max_bytes:
                        raise DownloadError(f"Response exceeded {self.max_bytes} bytes")
                    content_type = response.headers.get_content_type()
                    return Download(url, content, content_type, datetime.now(UTC))
            except HTTPError as exc:
                if exc.code == 429:
                    raise DownloadError("Source rate limit reached (HTTP 429)") from exc
                raise DownloadError(f"Source returned HTTP {exc.code}") from exc
            except URLError as exc:
                if attempt == 1:
                    raise DownloadError(f"Could not download {url}: {exc.reason}") from exc
                self.sleeper(0.25)
        raise AssertionError("unreachable")
