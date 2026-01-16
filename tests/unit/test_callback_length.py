from __future__ import annotations

import uuid

from apps.bot.ui.callbacks import (
    AccessCb,
    CategoryCb,
    DeliveryCb,
    GroupCb,
    InboxCb,
    LinkCb,
    LinkSelectCb,
    ReportCb,
    UserCb,
    UserDeliveryCb,
)


def _assert_cb_fits(cb) -> None:
    payload = cb.pack()
    assert len(payload.encode()) <= 64, payload


def test_callback_payload_lengths_fit_telegram_limit() -> None:
    category_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    chat_id = 9223372036854775807

    _assert_cb_fits(CategoryCb(action="detail", category_id=category_id))
    _assert_cb_fits(UserCb(action="open", user_id=user_id))
    _assert_cb_fits(LinkCb(action="category", category_id=category_id))
    _assert_cb_fits(LinkSelectCb(action="add_toggle", chat_id=chat_id, page=9))
    _assert_cb_fits(InboxCb(action="open", message_id=message_id))
    _assert_cb_fits(UserDeliveryCb(action="open", category_id=category_id))
    _assert_cb_fits(UserDeliveryCb(action="preset", category_id=category_id, value="interval|180"))
    _assert_cb_fits(UserDeliveryCb(action="preset", category_id=category_id, value="daily|18-00"))
    _assert_cb_fits(DeliveryCb(action="preset", category_id=category_id, value="daily|18-00"))
    _assert_cb_fits(AccessCb(action="category", category_id=category_id))
    _assert_cb_fits(AccessCb(action="user", user_id=user_id))
    _assert_cb_fits(AccessCb(action="grant", value="edit"))
    _assert_cb_fits(AccessCb(action="revoke"))
    _assert_cb_fits(GroupCb(action="detail", chat_id=chat_id))
    _assert_cb_fits(ReportCb(action="last", category_id=category_id, value="168"))
