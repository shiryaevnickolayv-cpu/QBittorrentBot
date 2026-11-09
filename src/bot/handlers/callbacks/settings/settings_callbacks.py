from aiogram import Bot, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _

from src.settings import Settings
from src.settings.enums import UserRolesEnum
from src.redis_helper.wrapper import RedisWrapper

from src.bot.filters import HasRole
from src.bot.filters.callbacks import SettingsMenu, Menu, EditClientMenu, ReloadSettingsMenu, ToggleSpeedLimit, CheckConnection
from src.bot.filters.callbacks import ClientSection, SettingEdit, SettingToggle, RatioAction

from src.client_manager.client_repo import ClientRepo


SECTION_SETTINGS = {
    "seeding": [
        ("max_ratio_enabled", "Max ratio enabled"),
        ("max_ratio", "Max ratio"),
        ("max_ratio_act", "When ratio is reached"),
        ("max_seeding_time_enabled", "Max seeding time enabled"),
        ("max_seeding_time", "Max seeding time, minutes"),
        ("max_inactive_seeding_time_enabled", "Max inactive seeding time enabled"),
        ("max_inactive_seeding_time", "Max inactive seeding time, minutes"),
    ],
    "queue": [
        ("queueing_enabled", "Queueing enabled"),
        ("max_active_downloads", "Max active downloads"),
        ("max_active_uploads", "Max active uploads"),
        ("max_active_torrents", "Max active torrents"),
    ],
    "speed": [
        ("dl_limit", "Download limit"),
        ("up_limit", "Upload limit"),
    ],
}

SECTION_TITLES = {
    "seeding": "Seeding",
    "queue": "Queue",
    "speed": "Speed",
}

RATIO_ACTIONS = {
    0: "Stop torrent",
    1: "Delete torrent",
    2: "Delete torrent and files",
    3: "Enable super seeding",
}

SETTING_PROMPTS = {
    "max_ratio": "Enter a ratio from 0 to 100 with at most one decimal place",
    "max_seeding_time": "Enter minutes from 0 to 100000",
    "max_inactive_seeding_time": "Enter minutes from 0 to 100000",
    "max_active_downloads": "Enter a whole number from 1 to 50",
    "max_active_uploads": "Enter a whole number from 1 to 50",
    "max_active_torrents": "Enter a whole number from 1 to 50",
    "dl_limit": "Enter download speed in MB/s from 0 to 1000 (0 means unlimited)",
    "up_limit": "Enter upload speed in MB/s from 0 to 1000 (0 means unlimited)",
}


def setting_section(key: str) -> str:
    return next(section for section, settings in SECTION_SETTINGS.items() if any(item[0] == key for item in settings))


def format_preference(key: str, value) -> str:
    if isinstance(value, bool):
        return _("✅ Enabled") if value else _("❌ Disabled")
    if key in {"max_seeding_time", "max_inactive_seeding_time"} and value == -1:
        return "∞"
    if key in {"dl_limit", "up_limit"}:
        return _("{value} MB/s").format(value=f"{value / 1024 / 1024:g}")
    if key == "max_ratio":
        return f"{value:.1f}"
    if key == "max_ratio_act":
        return _(RATIO_ACTIONS[value])
    return str(value)


async def show_client_settings(bot: Bot, chat_id: int, message_id: int, settings: Settings) -> None:
    repository_class = ClientRepo.get_client_manager(settings.client.type)
    speed_limit = await repository_class(settings).get_speed_limit_mode()
    speed_limit_status = _("✅ Enabled") if speed_limit else _("❌ Disabled")
    text = _("Edit {client_type} client settings\n\n**Speed Limit**: {speed_limit_status}").format(
        client_type=settings.client.type.value.title(),
        speed_limit_status=speed_limit_status,
    )
    buttons = [
        [InlineKeyboardButton(text=_("🌱 Seeding"), callback_data=ClientSection(section="seeding").pack())],
        [InlineKeyboardButton(text=_("📋 Queue"), callback_data=ClientSection(section="queue").pack())],
        [InlineKeyboardButton(text=_("🚀 Speed"), callback_data=ClientSection(section="speed").pack())],
        [InlineKeyboardButton(text=_("🐢 Toggle Speed Limit"), callback_data=ToggleSpeedLimit().pack())],
        [InlineKeyboardButton(text=_("✅ Check Client connection"), callback_data=CheckConnection().pack())],
        [InlineKeyboardButton(text=_("🔙 Settings"), callback_data=SettingsMenu().pack())],
        [InlineKeyboardButton(text=_("🏠 Menu"), callback_data=Menu().pack())],
    ]
    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def show_client_section(bot: Bot, chat_id: int, message_id: int, settings: Settings, section: str) -> None:
    repository_class = ClientRepo.get_client_manager(settings.client.type)
    preferences = await repository_class(settings).get_preferences()
    buttons = []
    for key, label in SECTION_SETTINGS[section]:
        text = _("{label}: {value}").format(label=_(label), value=format_preference(key, preferences[key]))
        if isinstance(preferences[key], bool):
            callback_data = SettingToggle(key=key).pack()
        else:
            callback_data = SettingEdit(key=key).pack()
        buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    buttons.extend([
        [InlineKeyboardButton(text=_("🔙 Client settings"), callback_data=EditClientMenu().pack())],
        [InlineKeyboardButton(text=_("🏠 Menu"), callback_data=Menu().pack())],
    ])
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=_(SECTION_TITLES[section]),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


def get_router():
    router = Router()

    @router.callback_query(SettingsMenu.filter(), HasRole(UserRolesEnum.Administrator))
    async def settings_callback(callback_query: CallbackQuery, callback_data: SettingsMenu, bot: Bot) -> None:
        await bot.edit_message_text(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id,
            text=_("QBittorrentBot Settings"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_("📥 Client Settings"), callback_data=EditClientMenu().pack())],
                [InlineKeyboardButton(text=_("🔄 Reload Settings"), callback_data=ReloadSettingsMenu().pack())],
                [InlineKeyboardButton(text=_("🏠 Menu"), callback_data=Menu().pack())],
            ]),
        )

    @router.callback_query(EditClientMenu.filter(), HasRole(UserRolesEnum.Administrator))
    async def edit_client_settings_callback(
        callback_query: CallbackQuery,
        callback_data: EditClientMenu,
        bot: Bot,
        settings: Settings,
        redis: RedisWrapper,
    ) -> None:
        await redis.delete(f"action:{callback_query.from_user.id}")
        await show_client_settings(bot, callback_query.from_user.id, callback_query.message.message_id, settings)
        await callback_query.answer()

    @router.callback_query(ClientSection.filter(), HasRole(UserRolesEnum.Administrator))
    async def client_section_callback(
        callback_query: CallbackQuery,
        callback_data: ClientSection,
        bot: Bot,
        settings: Settings,
        redis: RedisWrapper,
    ) -> None:
        await redis.delete(f"action:{callback_query.from_user.id}")
        await show_client_section(
            bot,
            callback_query.from_user.id,
            callback_query.message.message_id,
            settings,
            callback_data.section,
        )
        await callback_query.answer()

    @router.callback_query(SettingEdit.filter(), HasRole(UserRolesEnum.Administrator))
    async def setting_edit_callback(
        callback_query: CallbackQuery,
        callback_data: SettingEdit,
        settings: Settings,
        redis: RedisWrapper,
    ) -> None:
        section = setting_section(callback_data.key)
        back_button = InlineKeyboardButton(text=_("Cancel"), callback_data=ClientSection(section=section).pack())
        if callback_data.key == "max_ratio_act":
            buttons = [
                [InlineKeyboardButton(text=_(label), callback_data=RatioAction(value=value).pack())]
                for value, label in RATIO_ACTIONS.items()
            ]
            buttons.append([back_button])
            await callback_query.message.edit_text(_("Choose an action"), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
            await callback_query.answer()
            return

        await redis.set(f"action:{callback_query.from_user.id}", f"setting#{callback_data.key}")
        await callback_query.message.edit_text(_(SETTING_PROMPTS[callback_data.key]), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_button]]))
        await callback_query.answer()

    @router.callback_query(SettingToggle.filter(), HasRole(UserRolesEnum.Administrator))
    async def setting_toggle_callback(
        callback_query: CallbackQuery,
        callback_data: SettingToggle,
        bot: Bot,
        settings: Settings,
    ) -> None:
        repository_class = ClientRepo.get_client_manager(settings.client.type)
        manager = repository_class(settings)
        preferences = await manager.get_preferences()
        await manager.set_preferences({callback_data.key: not preferences[callback_data.key]})
        updated = await manager.get_preferences()
        value = updated[callback_data.key]
        await callback_query.answer(
            _("{key} is now {value}").format(key=callback_data.key, value=format_preference(callback_data.key, value)),
            show_alert=True,
        )
        await show_client_section(
            bot,
            callback_query.from_user.id,
            callback_query.message.message_id,
            settings,
            setting_section(callback_data.key),
        )

    @router.callback_query(RatioAction.filter(), HasRole(UserRolesEnum.Administrator))
    async def ratio_action_callback(
        callback_query: CallbackQuery,
        callback_data: RatioAction,
        bot: Bot,
        settings: Settings,
    ) -> None:
        repository_class = ClientRepo.get_client_manager(settings.client.type)
        manager = repository_class(settings)
        await manager.set_preferences({"max_ratio_act": callback_data.value})
        updated = await manager.get_preferences()
        value = updated["max_ratio_act"]
        await callback_query.answer(
            _("max_ratio_act is now {value}").format(value=format_preference("max_ratio_act", value)),
            show_alert=True,
        )
        await show_client_section(bot, callback_query.from_user.id, callback_query.message.message_id, settings, "seeding")

    @router.callback_query(ToggleSpeedLimit.filter(), HasRole(UserRolesEnum.Administrator))
    async def toggle_speed_limit_callback(callback_query: CallbackQuery, callback_data: ToggleSpeedLimit, bot: Bot, settings: Settings) -> None:
        repository_class = ClientRepo.get_client_manager(settings.client.type)
        await repository_class(settings).toggle_speed_limit()
        await show_client_settings(bot, callback_query.from_user.id, callback_query.message.message_id, settings)
        await callback_query.answer()

    @router.callback_query(CheckConnection.filter(), HasRole(UserRolesEnum.Administrator))
    async def check_connection_callback(callback_query: CallbackQuery, callback_data: CheckConnection, bot: Bot, settings: Settings) -> None:
        try:
            repository_class = ClientRepo.get_client_manager(settings.client.type)
            version = await repository_class(settings).check_connection()
            await callback_query.answer(
                _("✅ The connection works. QBittorrent version: {version}").format(version=version),
                show_alert=True,
            )
        except Exception:
            await callback_query.answer(_("❌ Unable to establish connection with QBittorrent"), show_alert=True)

    @router.callback_query(ReloadSettingsMenu.filter(), HasRole(UserRolesEnum.Administrator))
    async def reload_settings_callback(callback_query: CallbackQuery, callback_data: ReloadSettingsMenu, bot: Bot, settings: Settings) -> None:
        new_settings = Settings.load_settings()
        settings.update_from(new_settings)
        await callback_query.answer(_("✅ Settings Reloaded"), show_alert=True)

    return router
