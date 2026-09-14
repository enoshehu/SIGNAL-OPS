from email.message import Message
from urllib.error import URLError
import unittest

from signalops.http import HttpClient


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.headers = Message()
        self.headers["Content-Type"] = "application/zip"

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self.content[:size]


class HttpClientTests(unittest.TestCase):
    def test_retries_one_temporary_network_failure(self) -> None:
        calls = 0

        def opener(request: object, timeout: int) -> FakeResponse:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise URLError("temporary")
            return FakeResponse(b"downloaded")

        result = HttpClient(opener=opener, sleeper=lambda _: None).get(
            "https://example.invalid/data", headers={}, timeout=10
        )

        self.assertEqual(result.content, b"downloaded")
        self.assertEqual(result.content_type, "application/zip")
        self.assertEqual(calls, 2)
