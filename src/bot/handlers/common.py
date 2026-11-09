from typing import Optional
import logging

import psutil
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from src.redis_helper.wrapper import RedisWrapper
from src.settings import Settings
from src.client_manager.client_repo import ClientRepo
from src.utils import convert_size, get_user_from_config, paginate, status_icon, truncate_name
from src.settings.enums import UserRolesEnum
from src.bot.filters.callbacks import CategoryAction, CategoryMenu, ListMenu, ListPage, TorrentInfo, SettingsMenu, DeleteMenu, PauseResumeMenu, Menu

logger = logging.getLogger(__name__)


async def send_menu(bot: Bot, redis: RedisWrapper, settings: Settings, chat_id: int, message_id: Optional[int] = None) -> None:
    user = get_user_from_config(chat_id, settings)

    # Build buttons
    buttons = [
        [InlineKeyboardButton(text=_("📝 List"), callback_data=ListMenu().pack())]
    ]

    if user.role in [UserRolesEnum.Manager, UserRolesEnum.Administrator]:
        buttons += [
            [
                InlineKeyboardButton(
                    text=_("➕ Add Magnet"),
                    callback_data=CategoryAction(action="add_magnet").pack()
                ),
                InlineKeyboardButton(
                    text=_("➕ Add Torrent"),
                    callback_data=CategoryAction(action="add_torrent").pack()
                )
            ],
            [InlineKeyboardButton(text=_("⏯ Pause/Resume"), callback_data=PauseResumeMenu().pack())]
        ]

    if user.role == UserRolesEnum.Administrator:
        buttons += [
            [InlineKeyboardButton(text=_("🗑 Delete"), callback_data=DeleteMenu().pack())],
            [InlineKeyboardButton(text=_("📂 Categories"), callback_data=CategoryMenu().pack())],
            [InlineKeyboardButton(text=_("⚙️ Settings"), callback_data=SettingsMenu().pack())]
        ]

    await redis.delete(f"action:{chat_id}")
    if not await redis.exists(f"menu_keyboard:{chat_id}"):
        reply_markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=_("🏠 Menu"))]],
            resize_keyboard=True,
            is_persistent=True,
        )
        await bot.send_message(chat_id, _("Use the Menu button below to return here at any time"), reply_markup=reply_markup)
        await redis.set(f"menu_keyboard:{chat_id}", "1")

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=_("Welcome to QBittorrent Bot"),
                reply_markup=markup
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=_("Welcome to QBittorrent Bot"),
                reply_markup=markup
            )
    except Exception as e:
        logger.warning(f"Failed to edit menu message, sending new one: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=_("Welcome to QBittorrent Bot"),
            reply_markup=markup
        )


async def _edit_or_send(bot: Bot, chat_id: int, message_id: int, text: str, markup: InlineKeyboardMarkup) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


def _free_disk_space() -> int:
    try:
        return psutil.disk_usage("/media").free
    except OSError:
        return psutil.disk_usage("/").free


def _filter_counts(torrents) -> dict[str, int]:
    return {
        "downloading": sum(t.state in {"downloading", "forcedDL", "metaDL", "stalledDL", "queuedDL"} for t in torrents),
        "seeding": sum(t.state in {"uploading", "forcedUP", "stalledUP", "queuedUP"} for t in torrents),
        "completed": sum(t.progress >= 1 for t in torrents),
        "stopped": sum(t.state in {"stoppedDL", "stoppedUP"} for t in torrents),
        "all": len(torrents),
    }


def _navigation_row(status: str, page: int, total_pages: int) -> list[InlineKeyboardButton]:
    previous_page = max(1, page - 1)
    next_page = min(total_pages, page + 1)
    return [
        InlineKeyboardButton(
            text="⬅️" if page > 1 else "·",
            callback_data=ListPage(status=status, page=previous_page).pack(),
        ),
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data=ListPage(status=status, page=page).pack(),
        ),
        InlineKeyboardButton(
            text="➡️" if page < total_pages else "·",
            callback_data=ListPage(status=status, page=next_page).pack(),
        ),
    ]


def _torrent_button_text(torrent) -> str:
    text = f"{status_icon(torrent.state)} {torrent.progress:.0%} · {truncate_name(torrent.name)}"
    if torrent.state in {"downloading", "forcedDL", "metaDL"} and torrent.dlspeed > 0:
        text += f" · ⬇️ {convert_size(torrent.dlspeed)}/s"
    elif torrent.state in {"uploading", "forcedUP"} and torrent.upspeed > 0:
        text += f" · ⬆️ {convert_size(torrent.upspeed)}/s"
    return text


async def list_active_torrents(
    bot: Bot,
    chat_id: int,
    message_id: int,
    settings: Settings,
    callback: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
) -> None:
    repository_class = ClientRepo.get_client_manager(settings.client.type)
    manager = repository_class(settings)

    if callback is None and status_filter is None:
        torrents = await manager.get_torrents()
        counts = _filter_counts(torrents)
        filter_buttons = [
            ("⬇️ Downloading", "downloading"),
            ("⬆️ Seeding", "seeding"),
            ("✅ Completed", "completed"),
            ("⏸ Paused", "stopped"),
            ("📋 All", "all"),
        ]
        buttons = []
        for index in range(0, len(filter_buttons), 2):
            row = []
            for label, status in filter_buttons[index:index + 2]:
                text = _("{label} ({count})").format(label=_(label), count=counts[status])
                row.append(InlineKeyboardButton(text=text, callback_data=ListPage(status=status, page=1).pack()))
            buttons.append(row)
        buttons.append([InlineKeyboardButton(text=_("🏠 Menu"), callback_data=Menu().pack())])
        await _edit_or_send(bot, chat_id, message_id, _("Choose a section"), InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    torrents = await manager.get_torrents(status_filter=status_filter)
    back_and_menu = [
        InlineKeyboardButton(text=_("🔙 Sections"), callback_data=ListMenu().pack()),
        InlineKeyboardButton(text=_("🏠 Menu"), callback_data=Menu().pack()),
    ]

    if callback:
        buttons = [
            [InlineKeyboardButton(text=truncate_name(torrent.name), callback_data=f"{callback}:{torrent.hash}")]
            for torrent in torrents
        ]
        buttons.append(back_and_menu)
        await _edit_or_send(bot, chat_id, message_id, _("Choose a torrent:"), InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    if not torrents:
        await _edit_or_send(
            bot,
            chat_id,
            message_id,
            _("This section is empty"),
            InlineKeyboardMarkup(inline_keyboard=[back_and_menu]),
        )
        return

    page_items, page, total_pages = paginate(torrents, page)
    section_names = {
        "downloading": _("Downloading"),
        "seeding": _("Seeding"),
        "completed": _("Completed"),
        "stopped": _("Paused"),
        "all": _("All"),
    }
    header = _("{section}: {count} · ⬇️ {download_speed}/s · ⬆️ {upload_speed}/s · Free {free_space}").format(
        section=section_names[status_filter],
        count=len(torrents),
        download_speed=convert_size(sum(t.dlspeed for t in torrents)),
        upload_speed=convert_size(sum(t.upspeed for t in torrents)),
        free_space=convert_size(_free_disk_space()),
    )
    navigation = _navigation_row(status_filter, page, total_pages)
    buttons = [navigation]
    buttons.extend(
        [InlineKeyboardButton(text=_torrent_button_text(torrent), callback_data=TorrentInfo(torrent_hash=torrent.hash).pack())]
        for torrent in page_items
    )
    buttons.extend([_navigation_row(status_filter, page, total_pages), back_and_menu])
    await _edit_or_send(bot, chat_id, message_id, header, InlineKeyboardMarkup(inline_keyboard=buttons))


async def list_categories(
    bot: Bot,
    chat_id: int,
    message_id: int,
    settings: Settings,
    callback: str
):
    buttons = []

    repository_class_class = ClientRepo.get_client_manager(settings.client.type)
    categories = await repository_class_class(settings).get_categories()

    if categories is None:
        buttons.append([InlineKeyboardButton(text=_("🏠 Menu"), callback_data=Menu().pack())])

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=_("There are no categories"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

        return

    for i in categories:
        buttons.append([InlineKeyboardButton(text=i, callback_data=f"{callback}:{i}")])

    buttons.append([InlineKeyboardButton(text=_("🏠 Menu"), callback_data=Menu().pack())])

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=_("Choose a category:"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    except Exception:
        await bot.send_message(
            chat_id,
            _("Choose a category:"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
