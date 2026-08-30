import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("METRON_USERNAME", "u")
    monkeypatch.setenv("METRON_PASSWORD", "p")

    from comic_scraper.config import get_settings

    get_settings.cache_clear()

    with patch("comic_scraper.api.MetronClient"), patch("comic_scraper.api.LookupCache") as mock_cache:
        mock_cache.return_value.get.return_value = None
        from comic_scraper.api import app, state

        with TestClient(app) as c:
            state["service"]._client.get_issue_by_upc.return_value = None
            yield c


def parse_sse_events(body: str) -> list[dict]:
    return [
        json.loads(chunk[len("data: ") :])
        for chunk in body.strip().split("\n\n")
        if chunk.startswith("data: ")
    ]


def test_batch_rejects_more_than_max_items(client) -> None:
    items = [{"upc12": "759606086121"}] * 21
    response = client.post("/lookup/batch", json={"items": items})
    assert response.status_code == 400


def test_batch_streams_one_event_per_item(client) -> None:
    # Items now run concurrently (see _batch_event_stream), so events can
    # arrive in any order - the frontend places them by "index", not arrival
    # order, so assertions here sort by index rather than assuming order.
    response = client.post(
        "/lookup/batch",
        json={"items": [{"upc12": "111111111111"}, {"upc12": "222222222222", "ean5": "00121"}]},
    )
    assert response.status_code == 200

    events = sorted(parse_sse_events(response.text), key=lambda e: e["index"])
    assert [e["index"] for e in events] == [0, 1]
    assert [e["upc12"] for e in events] == ["111111111111", "222222222222"]
    assert events[1]["ean5"] == "00121"
    assert all(e["status"] == "not_found" for e in events)


def test_batch_reports_per_item_errors_without_aborting_the_stream(client) -> None:
    from comic_scraper.api import state

    # Keyed by the argument rather than call order - concurrent execution
    # means the two items' calls can land in either order.
    def fake_get_issue_by_upc(upc: str):
        if upc == "222222222222":
            raise RuntimeError("boom")
        return None

    state["service"]._client.get_issue_by_upc.side_effect = fake_get_issue_by_upc

    response = client.post(
        "/lookup/batch",
        json={"items": [{"upc12": "111111111111"}, {"upc12": "222222222222"}]},
    )
    events = {e["index"]: e for e in parse_sse_events(response.text)}
    assert events[0]["status"] == "not_found"
    assert events[1]["status"] == "error"
    assert "boom" in events[1]["message"]


def test_batch_processes_items_concurrently_not_sequentially(client) -> None:
    import threading

    from comic_scraper.api import state

    slow_started = threading.Event()
    fast_finished = threading.Event()

    def fake_get_issue_by_upc(upc: str):
        if upc == "111111111111":
            slow_started.set()
            # Blocks until the "fast" item (submitted second) has already
            # completed - only possible if they're running concurrently,
            # not queued one after another in a sequential for loop.
            assert fast_finished.wait(timeout=5)
            return None
        assert slow_started.wait(timeout=5)
        fast_finished.set()
        return None

    state["service"]._client.get_issue_by_upc.side_effect = fake_get_issue_by_upc

    response = client.post(
        "/lookup/batch",
        json={"items": [{"upc12": "111111111111"}, {"upc12": "222222222222"}]},
    )
    events = parse_sse_events(response.text)
    assert events[0]["upc12"] == "222222222222"
    assert events[1]["upc12"] == "111111111111"
