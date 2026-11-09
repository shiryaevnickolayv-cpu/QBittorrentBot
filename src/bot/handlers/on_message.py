import logging
import tempfile

from aiogram import F
from aiogram import Bot
from aiogram.types import Message
from aiogram.dispatcher.router import Router
from aiogram.filters import Command
from aiogram.utils.i18n import gettext as _

from src.client_manager.client_repo import ClientRepo
from src.settings import Settings
from src.bot.filters import IsAuthorizedUser, IsCommand
from src.redis_helper.wrapper import RedisWrapper
from src.utils import is_rename_blocked, validate_name

from .common import send_menu
from .callbacks.torrent_info import show_torrent_info


logger = logging.getLogger(__name__)


def get_router():
    router = Router()

    async def on_magnet(message: Message, redis: RedisWrapper, bot: Bot, settings: Settings):
        if message.text.startswith("magnet:?xt"):
            magnet_link = message.text.split("\n")
            category = (await redis.get(f"action:{message.from_user.id}")).split("#")[1]

            repository_class = ClientRepo.get_client_manager(settings.client.type)
            response = await repository_class(settings).add_magnet(
                magnet_link=magnet_link,
                category=category
            )

            if not response:
                await message.reply(_("Unable to add magnet link"))
                return

            await send_menu(bot, redis, settings, message.chat.id, message.message_id)
            await redis.delete(f"action:{message.from_user.id}")

        else:
            await message.reply(
                _("This magnet link is invalid! Retry")
            )


    async def on_torrent(message: Message, redis: RedisWrapper, bot: Bot, settings: Settings):
        if ".torrent" in message.document.file_name:
            with tempfile.TemporaryDirectory() as tempdir:
                name = f"{tempdir}/{message.document.file_name}"

                action = await redis.get(f"action:{message.from_user.id}") or ""
                category = action.split("#")[1] if action else None

                file = await bot.get_file(message.document.file_id)
                file_path = file.file_path
                await bot.download_file(file_path, name)

                repository_class = ClientRepo.get_client_manager(settings.client.type)
                response = await repository_class(settings).add_torrent(file_name=name, category=category)

                if not response:
                    await message.reply(_("Unable to add torrent file"))
                    return

            if not action:
                pass
                #await list_categories(bot, message.chat.id, message.message_id, settings, f"torrent_cat:{response}")
                #await redis.set(f"action:{message.from_user.id}", None)
                #return

            await send_menu(bot, redis, settings, message.chat.id, message.message_id)
            await redis.delete(f"action:{message.from_user.id}")

        else:
            await message.reply(
                _("This is not a torrent file! Retry")
            )


    async def on_category_name(message: Message, redis: RedisWrapper):
        await redis.set(f"action:{message.from_user.id}", f"category_dir#{message.text}")
        await message.reply(
            _("Please, send the path for the category {category_name}"
                .format(
                    category_name=message.text
                )
            )
        )


    async def on_category_directory(message: Message, action, redis: RedisWrapper, bot: Bot, settings: Settings):
        name: str = (await redis.get(f"action:{message.from_user.id}")).split("#")[1]

        repository_class = ClientRepo.get_client_manager(settings.client.type)

        if "modify" in action:
            await repository_class(settings).edit_category(name=name, save_path=message.text.replace("\\", ""))
            await send_menu(bot, redis, settings, message.chat.id, message.message_id)
            return

        await repository_class(settings).create_category(name=name, save_path=message.text.replace("\\", ""))
        await send_menu(bot, redis, settings, message.chat.id, message.message_id)


    async def on_rename(message: Message, action: str, redis: RedisWrapper, bot: Bot, settings: Settings):
        new_name = message.text
        if not validate_name(new_name):
            await message.reply(_("Invalid name: use 1-255 characters without \\ / : * ? \" < > | or control characters"))
            return

        repository_class = ClientRepo.get_client_manager(settings.client.type)
        manager = repository_class(settings)
        payload = action.split("#", 1)[1]
        torrent_hash = payload.split("|", 1)[0]
        torrent = await manager.get_torrent(torrent_hash)
        if is_rename_blocked(torrent.state):
            await message.reply(_("Stop the torrent before renaming it"))
            return

        if action.startswith("rename_torrent#"):
            await manager.rename_torrent(torrent_hash, new_name)
            success_text = _("Torrent name updated")
        else:
            old_path = payload.split("|", 1)[1]
            path_parts = old_path.split("/")
            path_parts[-1] = new_name
            new_path = "/".join(path_parts)
            files = await manager.get_torrent_files(torrent_hash)
            is_folder = any(file.name.startswith(old_path + "/") for file in files)
            if is_folder:
                await manager.rename_torrent_folder(torrent_hash, old_path, new_path)
            else:
                await manager.rename_torrent_file(torrent_hash, old_path, new_path)
            success_text = _("Folder or file renamed")

        await redis.delete(f"action:{message.from_user.id}")
        await message.reply(success_text)
        await show_torrent_info(bot, message.chat.id, message.message_id, settings, torrent_hash)

    @router.message(Command("menu"), IsAuthorizedUser())
    async def menu_command(message: Message, redis: RedisWrapper, bot: Bot, settings: Settings) -> None:
        await send_menu(bot, redis, settings, message.chat.id, message.message_id)

    @router.message(Command("cancel"), IsAuthorizedUser())
    async def cancel_command(message: Message, redis: RedisWrapper) -> None:
        await redis.delete(f"action:{message.from_user.id}")
        await message.reply(_("Cancelled"))

    @router.message(~F.from_user.is_bot, ~IsCommand(), IsAuthorizedUser())
    async def on_message(message: Message, redis: RedisWrapper, bot: Bot, settings: Settings) -> None:
        if message.text in {"🏠 Menu", "🏠 Меню"}:
            await send_menu(bot, redis, settings, message.chat.id, message.message_id)
            return

        action = await redis.get(f"action:{message.from_user.id}") or ""
        if message.text in {"Cancel", "Отмена"} and action:
            await redis.delete(f"action:{message.from_user.id}")
            await message.reply(_("Cancelled"))
            return

        if message.document and not action: # insert torrent without using UI
             await on_torrent(message, redis, bot, settings)

        elif "magnet" in action:
            await on_magnet(message, redis, bot, settings)

        elif "torrent" in action and message.document:
            await on_torrent(message, redis, bot, settings)

        elif action.startswith(("rename_torrent#", "rename_path#")):
            await on_rename(message, action, redis, bot, settings)

        elif action == "category_name":
            await on_category_name(message, redis)

        elif "category_dir" in action:
            await on_category_directory(message, action, redis, bot, settings)

        else:
            await message.reply(
                _("The command does not exist")
            )

    return router
