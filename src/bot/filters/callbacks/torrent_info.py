from aiogram.filters.callback_data import CallbackData


class TorrentInfo(CallbackData, prefix="torrentInfo"):
    torrent_hash: str


class Export(CallbackData, prefix="export"):
    torrent_hash: str

class EditTorrentCategory(CallbackData, prefix="edit_torrent_cat"):
    torrent_hash: str


class RenameMenu(CallbackData, prefix="rename_menu"):
    torrent_hash: str


class RenameTorrent(CallbackData, prefix="rename_torrent"):
    torrent_hash: str


class RenameFiles(CallbackData, prefix="rename_files"):
    torrent_hash: str


class RenamePath(CallbackData, prefix="rename_path"):
    torrent_hash: str
    path_index: int
