"""lib/admin_management.py 的單元測試（TDD RED 先行）。

見規格 docs/specs/pages/06-admin.md §lib/admin_management.py TDD cases 3–6。
"""
from __future__ import annotations

import pytest

from lib.models import Actor, AdminRole


# ── grade_label ───────────────────────────────────────────────────────────────

def test_grade_label_viewer():
    from lib.admin_management import grade_label
    assert grade_label(AdminRole.VIEWER) == "檢視者"


def test_grade_label_editor():
    from lib.admin_management import grade_label
    assert grade_label(AdminRole.EDITOR) == "編輯者"


def test_grade_label_super_admin():
    from lib.admin_management import grade_label
    assert grade_label(AdminRole.SUPER_ADMIN) == "超管"


def test_grade_label_root():
    from lib.admin_management import grade_label
    assert grade_label(AdminRole.ROOT) == "根管理員"


def test_grade_label_unknown_returns_str():
    from lib.admin_management import grade_label
    assert grade_label(77) == "77"


# ── can_manage_admin ──────────────────────────────────────────────────────────

def test_can_manage_admin_protected_target_always_false():
    """is_protected=True → 任何 actor 都不可管理（包含 SUPER_ADMIN）。"""
    from lib.admin_management import can_manage_admin
    actor = Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)
    assert not can_manage_admin(actor, target_is_protected=True)


def test_can_manage_admin_root_cannot_manage_protected():
    from lib.admin_management import can_manage_admin
    actor = Actor("root", "admin", grade=AdminRole.ROOT)
    assert not can_manage_admin(actor, target_is_protected=True)


def test_can_manage_admin_super_admin_can_manage_non_protected():
    from lib.admin_management import can_manage_admin
    actor = Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)
    assert can_manage_admin(actor, target_is_protected=False)


def test_can_manage_admin_editor_cannot_manage():
    from lib.admin_management import can_manage_admin
    actor = Actor("editor", "admin", grade=AdminRole.EDITOR)
    assert not can_manage_admin(actor, target_is_protected=False)


def test_can_manage_admin_viewer_cannot_manage():
    from lib.admin_management import can_manage_admin
    actor = Actor("viewer", "admin", grade=AdminRole.VIEWER)
    assert not can_manage_admin(actor, target_is_protected=False)


# ── seed_admins ────────────────────────────────────────────────────────────────

def test_seed_admins_contains_root():
    from lib.admin_management import seed_admins
    admins = seed_admins()
    root = next((a for a in admins if a["grade"] == AdminRole.ROOT), None)
    assert root is not None
    assert root["is_protected"] is True


def test_seed_admins_returns_list_of_dicts():
    from lib.admin_management import seed_admins
    admins = seed_admins()
    assert isinstance(admins, list)
    assert len(admins) >= 1
    first = admins[0]
    assert "username" in first
    assert "grade" in first
    assert "is_protected" in first


def test_seed_admins_non_root_not_protected():
    from lib.admin_management import seed_admins
    admins = seed_admins()
    for a in admins:
        if a["grade"] != AdminRole.ROOT:
            assert a["is_protected"] is False
