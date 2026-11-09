import os

from aiogram import Bot
from aiogram.types import Message
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup
from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.types import ReplyKeyboardRemove
from aiogram.dispatcher.router import Router
from aiogram.filters import CommandStart, Command
from aiogram.utils.i18n import gettext as _

import psutil

from src.redis_helper.wrapper import RedisWrapper
from src.utils import convert_size
from src.settings import Settings

from ..filters import IsAuthorizedUser
from .common import send_menu


def get_router():
    router = Router()

    @router.message(~IsAuthorizedUser())
    async def access_denied_message(message: Message) -> None:
        buttons = [
            [
                InlineKeyboardButton(
                    text="Github",
                    url="https://github.com/ch3p4ll3/QBittorrentBot/"
                )
            ]
        ]

        markup = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.reply(_("You are not authorized to use this bot"), reply_markup=markup)


    @router.message(CommandStart(), IsAuthorizedUser())
    async def start_command(message: Message, redis: RedisWrapper, bot: Bot, settings: Settings) -> None:
        """Start the bot."""
        await redis.delete(f"action:{message.from_user.id}")
        # Снимаем у клиента старую нижнюю клавиатуру, если она осталась от прежней версии
        sent = await message.answer(
            _("Welcome to QBittorrent Bot"),
            reply_markup=ReplyKeyboardRemove(),
        )
        await send_menu(bot, redis, settings, message.chat.id, sent.message_id)


    @router.message(Command("stats"), IsAuthorizedUser())
    async def stats_command(message: Message) -> None:
        try:
            cpu_temp = psutil.sensors_temperatures()['coretemp'][0].current
        except KeyError:
            cpu_temp = 0

        disk_path = next((p for p in ("/pool", "/media", "/") if os.path.isdir(p)), "/")
        disk = psutil.disk_usage(disk_path)

        stats_text = _(
            "<b>============SYSTEM============</b>\n<b>CPU Usage:</b> {cpu_usage}%\n" \
            "<b>CPU Temp:</b> {cpu_temp}°C\n<b>Free Memory:</b> {free_memory} of {total_memory} ({memory_percent}%)\n" \
            "<b>Disks usage:</b> {disk_used} of {disk_total} ({disk_percent}%)"
            .format(
                cpu_usage=psutil.cpu_percent(interval=None),
                cpu_temp=cpu_temp,
                free_memory=convert_size(psutil.virtual_memory().available),
                total_memory=convert_size(psutil.virtual_memory().total),
                memory_percent=psutil.virtual_memory().percent,
                disk_used=convert_size(disk.used),
                disk_total=convert_size(disk.total),
                disk_percent=disk.percent
            )
        )

        await message.reply(stats_text)

    return router
