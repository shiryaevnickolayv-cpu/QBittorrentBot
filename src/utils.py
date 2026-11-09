from math import log, floor
import datetime
from decimal import Decimal, InvalidOperation
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


def validate_name(name: str) -> bool:
    if not name or not name.strip() or len(name) > 255:
        return False
    forbidden = set('\\/:*?"<>|')
    return not any(char in forbidden or ord(char) < 32 or 127 <= ord(char) <= 159 for char in name)


def is_rename_blocked(state: str) -> bool:
    return state == "downloading" or state.startswith("checking") or state == "moving"


def parse_setting_value(key: str, text: str):
    try:
        value = Decimal(text.strip())
    except (InvalidOperation, TypeError, AttributeError):
        raise ValueError("Not a number") from None

    if not value.is_finite():
        raise ValueError("Not a finite number")

    if key == "max_ratio":
        if not 0 <= value <= 100 or value % Decimal("0.1") != 0:
            raise ValueError("Ratio must be between 0 and 100 with at most one decimal place")
        return float(value)

    integer_ranges = {
        "max_seeding_time": (0, 100000),
        "max_inactive_seeding_time": (0, 100000),
        "max_active_downloads": (1, 50),
        "max_active_uploads": (1, 50),
        "max_active_torrents": (1, 50),
    }
    if key in integer_ranges:
        minimum, maximum = integer_ranges[key]
        if value != value.to_integral_value() or not minimum <= value <= maximum:
            raise ValueError("Integer setting is out of range")
        return int(value)

    if key in {"dl_limit", "up_limit"}:
        if not 0 <= value <= 1000:
            raise ValueError("Speed must be between 0 and 1000 MB/s")
        return int(value * 1024 * 1024)

    raise ValueError("Unknown setting")
