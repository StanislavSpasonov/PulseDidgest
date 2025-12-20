from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class NavCb(CallbackData, prefix="nav"):
    action: str


class CategoryCb(CallbackData, prefix="cat"):
    action: str
    category_id: str = ""
    page: int = 0


class CategorySourceCb(CallbackData, prefix="catsrc"):
    action: str
    chat_id: int = 0
    page: int = 0


class CategoryDeliveryCb(CallbackData, prefix="catdel"):
    action: str
    mode: str = ""
    value: str = ""


class GroupCb(CallbackData, prefix="grp"):
    action: str
    chat_id: int = 0
    page: int = 0


class GroupSearchCb(CallbackData, prefix="grps"):
    action: str
    page: int = 0


class LinkCb(CallbackData, prefix="link"):
    action: str
    category_id: str = ""
    chat_id: int = 0
    page: int = 0


class DeliveryCb(CallbackData, prefix="del"):
    action: str
    category_id: str = ""
    value: str = ""


class ReportCb(CallbackData, prefix="rep"):
    action: str
    category_id: str = ""
    value: str = ""


class SettingsCb(CallbackData, prefix="set"):
    action: str
