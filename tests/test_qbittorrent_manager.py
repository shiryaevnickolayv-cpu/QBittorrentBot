import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.client_manager.qbittorrent_manager.qbittorrent_manager import QbittorrentManager


class FakeAsyncClient:
    def __init__(self):
        self.client = SimpleNamespace(torrents_stop=Mock(), torrents_start=Mock())
        self.call = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.mark.parametrize(
    ("method", "arguments", "client_method", "hashes"),
    [
        ("pause", ("abc",), "torrents_stop", "abc"),
        ("resume", ("abc",), "torrents_start", "abc"),
        ("pause_all", (), "torrents_stop", "all"),
        ("resume_all", (), "torrents_start", "all"),
    ],
)
def test_pause_resume_use_current_api(method, arguments, client_method, hashes):
    manager = QbittorrentManager(SimpleNamespace())
    client = FakeAsyncClient()
    manager._client = lambda: client

    asyncio.run(getattr(manager, method)(*arguments))

    expected_method = getattr(client.client, client_method)
    client.call.assert_awaited_once_with(expected_method, torrent_hashes=hashes)
