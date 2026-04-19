import inspect

import http_client


def test_get_forwards_timeout_to_urlopen(monkeypatch) -> None:
    captured: dict[str, float | None] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self) -> bytes:
            return b"ok"

    def fake_urlopen(url, *, timeout=None):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(http_client.urllib.request, "urlopen", fake_urlopen)
    http_client.get("http://x", timeout=7.5)
    assert captured["timeout"] == 7.5


def test_get_signature_has_timeout() -> None:
    sig = inspect.signature(http_client.get)
    assert "timeout" in sig.parameters
