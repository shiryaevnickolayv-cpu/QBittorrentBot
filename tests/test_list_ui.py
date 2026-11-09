from pathlib import Path
from types import SimpleNamespace

import pytest
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import I18n

from src.bot.handlers import common
from src.bot.filters.callbacks import ListPage, ListSelect
from src.settings.enums import ClientTypeEnum

LOCALES = Path(__file__).resolve().parent.parent / "src" / "locales"


@pytest.fixture()
def i18n_context():
    i18n = I18n(path=LOCALES, default_locale="en", domain="messages")
    with i18n.context() as ctx:
        ctx.current_locale = "ru"
        yield ctx


def torrent(index: int, state: str = "queuedUP", progress: float = 1.0, dlspeed: int = 0, upspeed: int = 0):
    return SimpleNamespace(
        hash=f"{index:040x}",
        name=f"Торрент номер {index} с довольно длинным названием",
        state=state,
        progress=progress,
        dlspeed=dlspeed,
        upspeed=upspeed,
    )


class FakeManager:
    def __init__(self, torrents):
        self.torrents = torrents

    async def get_torrents(self, status_filter=None):
        return self.torrents


class FakeBot:
    def __init__(self):
        self.calls = []

    async def edit_message_text(self, chat_id, message_id, text, reply_markup=None):
        self.calls.append(("edit", text, reply_markup))

    async def send_message(self, chat_id, text, reply_markup=None):
        self.calls.append(("send", text, reply_markup))


def settings():
    return SimpleNamespace(
        client=SimpleNamespace(type=ClientTypeEnum.QBittorrent),
        users=[],
    )


def run(coro):
    import asyncio

    return asyncio.get_event_loop().run_until_complete(coro)


def render(monkeypatch, torrents, **kwargs):
    manager = FakeManager(torrents)
    monkeypatch.setattr(
        common.ClientRepo, "get_client_manager", classmethod(lambda cls, _type: lambda _settings: manager)
    )
    monkeypatch.setattr(common, "_free_disk_space", lambda: 1024 ** 4)
    bot = FakeBot()
    run(common.list_active_torrents(bot, 1, 1, settings(), **kwargs))
    _, text, markup = bot.calls[-1]
    assert isinstance(markup, InlineKeyboardMarkup)
    return text, markup


def test_sections_screen(monkeypatch, i18n_context):
    text, markup = render(monkeypatch, [torrent(i) for i in range(5)])
    assert "Выберите раздел" in text
    statuses = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert any(status.startswith(ListPage(status="downloading", page=1).pack()) for status in statuses)
    assert any(status.startswith(ListPage(status="stopped", page=1).pack()) for status in statuses)


def test_paginated_list_rows_are_flat_buttons(monkeypatch, i18n_context):
    """Регрессия: кнопки торрентов должны лежать по одной в ряду, а не плоским списком."""
    text, markup = render(monkeypatch, [torrent(i) for i in range(20)], status_filter="all", page=2)
    rows = markup.inline_keyboard
    nav_labels = [button.text for button in rows[0]]
    assert "2/3" in nav_labels
    assert len(rows) == 1 + 8 + 2  # навигация сверху, 8 торрентов, навигация и меню снизу
    for row in rows:
        assert isinstance(row, list)
        for button in row:
            assert button.text
    assert rows[1][0].callback_data.startswith("torrentInfo:")


def test_select_mode_is_paginated(monkeypatch, i18n_context):
    text, markup = render(monkeypatch, [torrent(i) for i in range(20)], callback="pause", status_filter="all", page=1)
    rows = markup.inline_keyboard
    assert "Выбери торрент: 20 · 1/3" in text
    assert len(rows) == 1 + 8 + 2
    assert rows[1][0].callback_data.startswith("pause:")


def test_last_page_clamps(monkeypatch, i18n_context):
    text, markup = render(monkeypatch, [torrent(i) for i in range(9)], status_filter="all", page=99)
    nav_labels = [button.text for button in markup.inline_keyboard[0]]
    assert "2/2" in nav_labels


def test_empty_section(monkeypatch, i18n_context):
    text, markup = render(monkeypatch, [], status_filter="downloading", page=1)
    assert "пусто" in text.lower() or "Пусто" in text
    assert len(markup.inline_keyboard) == 1


def test_select_page_callback_data_roundtrip():
    packed = ListSelect(action="pause", status="all", page=3).pack()
    restored = ListSelect.unpack(packed)
    assert (restored.action, restored.status, restored.page) == ("pause", "all", 3)
