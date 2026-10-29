import json

import pytest

from llm_finance.sources import fetch_companyfacts, fetch_litellm


def test_explicit_sec_download_keeps_source_bytes_and_receipt(monkeypatch, tmp_path):
    calls = []

    class Response:
        content = b'{"facts": {}, "cik": 789019}'

        def raise_for_status(self):
            pass

        def json(self):
            return json.loads(self.content)

    def get(url, headers, timeout):
        calls.append((url, headers, timeout))
        return Response()

    monkeypatch.setattr("llm_finance.sources.requests.get", get)
    path = tmp_path / "sec.json"
    fetch_companyfacts("789019", path, "Research contact@unit.test")
    assert calls[0][0].endswith("CIK0000789019.json")
    assert calls[0][1]["User-Agent"] == "Research contact@unit.test"
    assert path.read_bytes() == Response.content
    receipt = json.loads((tmp_path / "sec.json.source.json").read_text())
    assert receipt["historical_availability_certified"] is False
    assert len(receipt["sha256"]) == 64
    with pytest.raises(ValueError, match="already exists"):
        fetch_companyfacts("789019", path, "Research contact@unit.test")
    assert len(calls) == 1


def test_http_error_never_leaves_a_successful_snapshot(monkeypatch, tmp_path):
    import requests

    class Response:
        def raise_for_status(self):
            raise requests.HTTPError("synthetic service error")

    monkeypatch.setattr("llm_finance.sources.requests.get", lambda *a, **k: Response())
    with pytest.raises(requests.HTTPError):
        fetch_litellm("a" * 40, tmp_path / "snapshot.json")
    assert list(tmp_path.iterdir()) == []
