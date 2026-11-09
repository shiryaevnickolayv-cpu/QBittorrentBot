from aiogram.filters.callback_data import CallbackData


class ListMenu(CallbackData, prefix="list_menu"):
    pass


class ListPage(CallbackData, prefix="list_page"):
    status: str
    page: int


class ListSelect(CallbackData, prefix="list_select"):
    action: str
    status: str
    page: int


class Menu(CallbackData, prefix="menu"):
    pass
