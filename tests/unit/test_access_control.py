from __future__ import annotations

from src.application.services.access_control import can_edit, can_use


def test_can_use_admin_active():
    assert can_use("admin", "active", False, None) is True


def test_can_use_owner_active():
    assert can_use("user", "active", True, None) is True


def test_can_use_acl_use():
    assert can_use("user", "active", False, "use") is True
    assert can_edit("user", "active", False, "use") is False


def test_can_edit_acl_edit():
    assert can_use("user", "active", False, "edit") is True
    assert can_edit("user", "active", False, "edit") is True


def test_blocked_cannot_use():
    assert can_use("admin", "blocked", True, "edit") is False
    assert can_edit("admin", "blocked", True, "edit") is False
