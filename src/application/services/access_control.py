from __future__ import annotations

from typing import Optional


def can_use(
    role: str,
    status: str,
    is_owner: bool,
    acl_permission: Optional[str],
) -> bool:
    if status != "active":
        return False
    if role == "admin":
        return True
    if is_owner:
        return True
    return acl_permission in {"use", "edit"}


def can_edit(
    role: str,
    status: str,
    is_owner: bool,
    acl_permission: Optional[str],
) -> bool:
    if status != "active":
        return False
    if role == "admin":
        return True
    if is_owner:
        return True
    return acl_permission == "edit"
