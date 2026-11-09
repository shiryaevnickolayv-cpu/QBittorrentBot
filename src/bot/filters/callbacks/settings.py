from aiogram.filters.callback_data import CallbackData


class SettingsMenu(CallbackData, prefix="settings"):
    pass


class EditClientMenu(CallbackData, prefix="edit_client"):
    pass


class ReloadSettingsMenu(CallbackData, prefix="reload_settings"):
    pass


class ToggleSpeedLimit(CallbackData, prefix="toggle_speed_limit"):
    pass

class CheckConnection(CallbackData, prefix="check_connection"):
    pass


class ClientSection(CallbackData, prefix="client_section"):
    section: str


class SettingEdit(CallbackData, prefix="setting_edit"):
    key: str


class SettingToggle(CallbackData, prefix="setting_toggle"):
    key: str


class RatioAction(CallbackData, prefix="ratio_action"):
    value: int
