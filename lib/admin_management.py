"""管理員管理純函式：grade 標籤、操作權限判斷、種子資料。

見規格 docs/specs/pages/06-admin.md §lib/admin_management.py。
"""
from __future__ import annotations

from typing import List

from lib.models import Actor, AdminRole

_GRADE_LABELS = {
    AdminRole.VIEWER:      "檢視者",
    AdminRole.EDITOR:      "編輯者",
    AdminRole.SUPER_ADMIN: "超管",
    AdminRole.ROOT:        "根管理員",
}


def grade_label(grade: int) -> str:
    """grade 數值 → 繁中顯示標籤；未知 grade 退回 str(grade)。"""
    return _GRADE_LABELS.get(grade, str(grade))


def can_manage_admin(actor: Actor, target_is_protected: bool) -> bool:
    """actor 是否可管理該目標管理員。

    - target_is_protected=True（ROOT）→ 永遠 False（任何人不可操作）
    - actor.grade >= SUPER_ADMIN → True；其餘 → False
    """
    if target_is_protected:
        return False
    return (actor.grade or 0) >= AdminRole.SUPER_ADMIN


def seed_admins() -> List[dict]:
    """開發用種子管理員清單（靜態，上線後由 API 取代）。"""
    return [
        {"username": "root",        "grade": AdminRole.ROOT,        "is_protected": True},
        {"username": "super_admin", "grade": AdminRole.SUPER_ADMIN, "is_protected": False},
        {"username": "editor",      "grade": AdminRole.EDITOR,      "is_protected": False},
        {"username": "viewer",      "grade": AdminRole.VIEWER,      "is_protected": False},
    ]
