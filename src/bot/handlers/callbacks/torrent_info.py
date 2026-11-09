from aiogram import Bot, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram.utils.i18n import gettext as _

from src.client_manager.client_repo import ClientRepo
from src.settings import Settings
from src.redis_helper.wrapper import RedisWrapper
from src.utils import convert_size, convert_eta, format_progress, escape_html, is_rename_blocked

from src.bot.filters.callbacks import TorrentInfo, Export, Pause, Resume, DeleteOne, Menu, EditTorrentCategory
from src.bot.filters.callbacks import RenameMenu, RenameTorrent, RenameFiles, RenamePath
from src.bot.handlers.common import list_categories


def top_level_paths(files) -> list[tuple[str, bool]]:
    paths = {}
    for file in files:
        name = file.name
        top_level = name.split("/", 1)[0]
        paths[top_level] = paths.get(top_level, False) or "/" in name
    return sorted(paths.items())


async def show_torrent_info(bot: Bot, chat_id: int, message_id: int, settings: Settings, torrent_hash: str) -> None:
    repository_class = ClientRepo.get_client_manager(settings.client.type)
    torrent = await repository_class(settings).get_torrent(torrent_hash)

    text_to_send = f"{escape_html(torrent.name)}\n"
    if torrent.progress == 1:
        text_to_send += _("<b>COMPLETED</b>\n")
    else:
        text_to_send += format_progress(torrent.progress)

    if "stalled" not in torrent.state:
        text_to_send += _("<b>State:</b> {current_state} \n<b>Download Speed:</b> {download_speed}/с\n").format(
            current_state=escape_html(torrent.state.capitalize()),
            download_speed=convert_size(torrent.dlspeed),
        )

    text_to_send += _("<b>Size:</b> {torrent_size}\n").format(torrent_size=convert_size(torrent.size))
    if "stalled" not in torrent.state:
        text_to_send += _("<b>ETA:</b> {torrent_eta}\n").format(torrent_eta=convert_eta(int(torrent.eta)))
    if torrent.category:
        text_to_send += _("<b>Category:</b> {torrent_category}\n").format(torrent_category=escape_html(torrent.category))

    buttons = [
        [InlineKeyboardButton(text=_("💾 Export torrent"), callback_data=Export(torrent_hash=torrent_hash).pack())],
        [InlineKeyboardButton(text=_("📝 Edit Category"), callback_data=EditTorrentCategory(torrent_hash=torrent_hash).pack())],
        [InlineKeyboardButton(text=_("✏️ Rename"), callback_data=RenameMenu(torrent_hash=torrent_hash).pack())],
        [InlineKeyboardButton(text=_("⏸ Pause"), callback_data=Pause(torrent_hash=torrent_hash).pack())],
        [InlineKeyboardButton(text=_("▶️ Resume"), callback_data=Resume(torrent_hash=torrent_hash).pack())],
        [InlineKeyboardButton(text=_("🗑 Delete"), callback_data=DeleteOne(torrent_hash=torrent_hash).pack())],
        [InlineKeyboardButton(text=_("🏠 Menu"), callback_data=Menu().pack())],
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text_to_send, reply_markup=markup)
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text_to_send, reply_markup=markup)


def get_router():
    router = Router()

    @router.callback_query(TorrentInfo.filter())
    async def torrent_info_callback(
        callback_query: CallbackQuery,
        callback_data: TorrentInfo,
        settings: Settings,
        bot: Bot,
        redis: RedisWrapper,
    ) -> None:
        await redis.delete(f"action:{callback_query.from_user.id}")
        await show_torrent_info(
            bot,
            callback_query.from_user.id,
            callback_query.message.message_id,
            settings,
            callback_data.torrent_hash,
        )
        await callback_query.answer()

    @router.callback_query(RenameMenu.filter())
    async def rename_menu_callback(
        callback_query: CallbackQuery,
        callback_data: RenameMenu,
        settings: Settings,
        redis: RedisWrapper,
    ) -> None:
        repository_class = ClientRepo.get_client_manager(settings.client.type)
        torrent = await repository_class(settings).get_torrent(callback_data.torrent_hash)
        if is_rename_blocked(torrent.state):
            await callback_query.answer(_("Stop the torrent before renaming it"), show_alert=True)
            return

        await redis.delete(f"action:{callback_query.from_user.id}")
        buttons = [
            [InlineKeyboardButton(text=_("📛 Torrent name"), callback_data=RenameTorrent(torrent_hash=callback_data.torrent_hash).pack())],
            [InlineKeyboardButton(text=_("📁 Folder/file on disk"), callback_data=RenameFiles(torrent_hash=callback_data.torrent_hash).pack())],
            [InlineKeyboardButton(text=_("🔙 Back"), callback_data=TorrentInfo(torrent_hash=callback_data.torrent_hash).pack())],
            [InlineKeyboardButton(text=_("🏠 Menu"), callback_data=Menu().pack())],
        ]
        await callback_query.message.edit_text(_("Choose what to rename"), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback_query.answer()

    @router.callback_query(RenameTorrent.filter())
    async def rename_torrent_callback(
        callback_query: CallbackQuery,
        callback_data: RenameTorrent,
        settings: Settings,
        redis: RedisWrapper,
    ) -> None:
        repository_class = ClientRepo.get_client_manager(settings.client.type)
        torrent = await repository_class(settings).get_torrent(callback_data.torrent_hash)
        if is_rename_blocked(torrent.state):
            await callback_query.answer(_("Stop the torrent before renaming it"), show_alert=True)
            return

        await redis.set(f"action:{callback_query.from_user.id}", f"rename_torrent#{callback_data.torrent_hash}")
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=_("Cancel"), callback_data=RenameMenu(torrent_hash=callback_data.torrent_hash).pack())
        ]])
        await callback_query.message.edit_text(
            _("Send the new torrent name. The name will change only in the client; files on disk will remain unchanged."),
            reply_markup=markup,
        )
        await callback_query.answer()

    @router.callback_query(RenameFiles.filter())
    async def rename_files_callback(
        callback_query: CallbackQuery,
        callback_data: RenameFiles,
        settings: Settings,
        redis: RedisWrapper,
    ) -> None:
        repository_class = ClientRepo.get_client_manager(settings.client.type)
        manager = repository_class(settings)
        torrent = await manager.get_torrent(callback_data.torrent_hash)
        if is_rename_blocked(torrent.state):
            await callback_query.answer(_("Stop the torrent before renaming it"), show_alert=True)
            return

        files = await manager.get_torrent_files(callback_data.torrent_hash)
        paths = top_level_paths(files)
        buttons = [
            [InlineKeyboardButton(
                text=("📁 " if is_folder else "📄 ") + path,
                callback_data=RenamePath(torrent_hash=callback_data.torrent_hash, path_index=index).pack(),
            )]
            for index, (path, is_folder) in enumerate(paths)
        ]
        buttons.append([InlineKeyboardButton(text=_("🔙 Back"), callback_data=RenameMenu(torrent_hash=callback_data.torrent_hash).pack())])
        await redis.delete(f"action:{callback_query.from_user.id}")
        await callback_query.message.edit_text(_("Choose a folder or file"), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback_query.answer()

    @router.callback_query(RenamePath.filter())
    async def rename_path_callback(
        callback_query: CallbackQuery,
        callback_data: RenamePath,
        settings: Settings,
        redis: RedisWrapper,
    ) -> None:
        repository_class = ClientRepo.get_client_manager(settings.client.type)
        manager = repository_class(settings)
        torrent = await manager.get_torrent(callback_data.torrent_hash)
        if is_rename_blocked(torrent.state):
            await callback_query.answer(_("Stop the torrent before renaming it"), show_alert=True)
            return

        paths = top_level_paths(await manager.get_torrent_files(callback_data.torrent_hash))
        if callback_data.path_index >= len(paths):
            await callback_query.answer(_("The selected path no longer exists"), show_alert=True)
            return
        old_path = paths[callback_data.path_index][0]
        await redis.set(
            f"action:{callback_query.from_user.id}",
            f"rename_path#{callback_data.torrent_hash}|{old_path}",
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=_("Cancel"), callback_data=RenameFiles(torrent_hash=callback_data.torrent_hash).pack())
        ]])
        await callback_query.message.edit_text(_("Send only the new name, without a path"), reply_markup=markup)
        await callback_query.answer()

    @router.callback_query(Export.filter())
    async def export_callback(callback_query: CallbackQuery, callback_data: Export, settings: Settings, bot: Bot) -> None:
        repository_class = ClientRepo.get_client_manager(settings.client.type)
        file_bytes = await repository_class(settings).export_torrent(callback_data.torrent_hash)
        await bot.send_document(callback_query.from_user.id, BufferedInputFile(file_bytes.read(), file_bytes.name))

    @router.callback_query(EditTorrentCategory.filter())
    async def edit_torrent_cateogry(callback_query: CallbackQuery, callback_data: EditTorrentCategory, settings: Settings, bot: Bot):
        await list_categories(bot, callback_query.from_user.id, callback_query.message.message_id, settings, f"torrent_cat:{callback_data.torrent_hash}")

    return router
