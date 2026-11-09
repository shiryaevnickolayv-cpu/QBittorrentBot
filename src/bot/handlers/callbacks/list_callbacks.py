from aiogram import Bot, Router
from aiogram.types import CallbackQuery

from src.bot.filters.callbacks import ListMenu, ListPage, Menu
from src.bot.handlers.common import list_active_torrents, send_menu
from src.settings import Settings
from src.redis_helper.wrapper import RedisWrapper


def get_router():
    router = Router()

    @router.callback_query(ListMenu.filter())
    async def list_callback(callback_query: CallbackQuery, callback_data: ListMenu, settings: Settings, bot: Bot) -> None:
        await list_active_torrents(bot, callback_query.from_user.id, callback_query.message.message_id, settings)
        await callback_query.answer()

    @router.callback_query(ListPage.filter())
    async def list_by_status_callback(callback_query: CallbackQuery, callback_data: ListPage, settings: Settings, bot: Bot) -> None:
        await list_active_torrents(
            bot,
            callback_query.from_user.id,
            callback_query.message.message_id,
            settings,
            status_filter=callback_data.status,
            page=callback_data.page,
        )
        await callback_query.answer()

    @router.callback_query(Menu.filter())
    async def menu_callback(callback_query: CallbackQuery, callback_data: Menu, bot: Bot, redis: RedisWrapper, settings: Settings) -> None:
        await send_menu(bot, redis, settings, callback_query.from_user.id, callback_query.message.message_id)
        await callback_query.answer()

    return router
