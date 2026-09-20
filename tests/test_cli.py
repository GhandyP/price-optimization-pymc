from __future__ import annotations

import pytest

from price_optimizer import cli


class _FakeServer:
    def __init__(self, started: bool) -> None:
        self.started = started


@pytest.fixture
def opened_urls(monkeypatch) -> list[str]:
    urls: list[str] = []
    monkeypatch.setattr(cli.webbrowser, "open", urls.append)
    return urls


def test_browser_opens_once_the_server_is_started(monkeypatch, opened_urls):
    monkeypatch.setattr(cli, "BROWSER_OPEN_TIMEOUT_SECONDS", 1.0)

    cli._open_browser_when_ready(_FakeServer(started=True), "http://127.0.0.1:8000")

    assert opened_urls == ["http://127.0.0.1:8000"]


def test_browser_does_not_open_while_the_server_is_still_starting(monkeypatch, opened_urls):
    monkeypatch.setattr(cli, "BROWSER_OPEN_TIMEOUT_SECONDS", 0.05)

    cli._open_browser_when_ready(_FakeServer(started=False), "http://127.0.0.1:8000")

    assert opened_urls == []
