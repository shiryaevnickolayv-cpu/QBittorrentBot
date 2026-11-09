from math import log, floor
import datetime
import re

from src.settings.user import User


def get_user_from_config(user_id: int, settings: "Settings") -> User:
    return next(
        iter(
            [i for i in settings.users if i.user_id == user_id]
        ), None
    )


def convert_size(size_bytes) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(floor(log(size_bytes, 1024)))
    p = pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


def convert_eta(n) -> str:
    return str(datetime.timedelta(seconds=n))


def format_progress(progress: float, width: int = 20) -> str:
    """
    progress: float from 0.0 to 1.0
    """
    progress = max(0.0, min(progress, 1.0))
    filled = int(progress * width)

    bar = "█" * filled + "░" * (width - filled)
    percent = int(progress * 100)

    return f"{percent:3d}%|{bar}|\n"


def inejct_new_config_data(json_data: dict):
    json_data['redis'] = {
        'url': None
    }

    for index, i in enumerate(json_data['users']):
        i['notification_filter'] = []
        json_data['users'][index] = i


def escape_markdown(text: str):
    # Characters that need escaping in Telegram MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


MAX_NAME_LEN = 34
TORRENTS_PER_PAGE = 8


def status_icon(state: str) -> str:
    icons = {
        "downloading": "⬇️",
        "forcedDL": "⬇️",
        "metaDL": "⬇️",
        "stalledDL": "🔌",
        "queuedDL": "🕓",
        "uploading": "⬆️",
        "forcedUP": "⬆️",
        "stalledUP": "💤",
        "queuedUP": "⏳",
        "stoppedDL": "⏸",
        "stoppedUP": "⏸",
        "checkingUP": "🔄",
        "checkingDL": "🔄",
        "checkingResumeData": "🔄",
        "moving": "🔄",
        "error": "⚠️",
        "missingFiles": "⚠️",
    }
    return icons.get(state, "❓")


def paginate(items, page: int, per_page: int = TORRENTS_PER_PAGE):
    if per_page < 1:
        raise ValueError("per_page must be positive")
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    start = (page - 1) * per_page
    return items[start:start + per_page], page, total_pages


def truncate_name(name: str, max_length: int = MAX_NAME_LEN) -> str:
    if len(name) <= max_length:
        return name
    return name[:max_length - 1] + "…"
