from __future__ import annotations

from datetime import datetime, timezone

import lib.models as _m
from lib.models import Actor, AdminRole, Record, can_edit, can_write


def _record(created_by: str = "alice") -> Record:
    now = datetime(2026, 7, 18, tzinfo=timezone.utc)
    return Record(
        id=1,
        title="溫度",
        value=25.0,
        category="感測器",
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


# --- AdminRole 常數（data-source §AdminRole）---

def test_admin_role_viewer():
    assert AdminRole.VIEWER == 0


def test_admin_role_editor():
    assert AdminRole.EDITOR == 50


def test_admin_role_super_admin():
    assert AdminRole.SUPER_ADMIN == 100


def test_admin_role_root():
    assert AdminRole.ROOT == 999


# --- can_edit(data-source §權限純函式、§落地順序 1) ---

def test_can_edit_admin_always_true():
    # Admin（grade>0）可編輯任何資料（即使非其建立）
    assert can_edit(_record(created_by="bob"), Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)) is True


def test_can_edit_creator_true():
    assert can_edit(_record(created_by="alice"), Actor("alice", "user")) is True


def test_can_edit_other_user_false():
    assert can_edit(_record(created_by="alice"), Actor("bob", "user")) is False


# --- grade 欄位與 admin_role 對齊後端 ---

def test_actor_has_grade_field():
    """Actor 有 grade 欄位，預設 None。"""
    a = Actor("alice", "user")
    assert hasattr(a, "grade")
    assert a.grade is None


def test_actor_grade_can_be_set():
    a = Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)
    assert a.grade == AdminRole.SUPER_ADMIN


def test_can_edit_super_admin_true():
    assert can_edit(_record(created_by="bob"), Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)) is True


def test_can_edit_editor_admin_true():
    assert can_edit(_record(created_by="bob"), Actor("editor", "admin", grade=AdminRole.EDITOR)) is True


def test_can_edit_viewer_admin_false():
    """Viewer admin（grade=0）唯讀，不可編輯任何資料。"""
    assert can_edit(_record(created_by="bob"), Actor("viewer", "admin", grade=AdminRole.VIEWER)) is False


def test_can_edit_viewer_admin_own_record_also_false():
    """Viewer admin（grade=0）即使是自己建立的資料也不可編輯（唯讀限制）。"""
    assert can_edit(_record(created_by="viewer"), Actor("viewer", "admin", grade=AdminRole.VIEWER)) is False


# --- can_write(actor)：寫入權限單一真相 ---

def test_can_write_super_admin_true():
    assert can_write(Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)) is True


def test_can_write_root_true():
    assert can_write(Actor("root", "admin", grade=AdminRole.ROOT)) is True


def test_can_write_editor_true():
    assert can_write(Actor("editor", "admin", grade=AdminRole.EDITOR)) is True


def test_can_write_viewer_false():
    assert can_write(Actor("viewer", "admin", grade=AdminRole.VIEWER)) is False


def test_can_write_user_role_false():
    """role='user' → False（latent 防線）。"""
    assert can_write(Actor("alice", "user")) is False


def test_can_write_none_grade_admin_false():
    """grade=None + admin → (None or 0) > 0 → False（未知 grade 拒絕寫入，安全預設）。"""
    assert can_write(Actor("admin", "admin", grade=None)) is False


def test_can_edit_admin_delegates_to_can_write(monkeypatch):
    """can_edit admin 分支必須委派 can_write，不得重寫字面條件（data-source §權限純函式）。"""
    calls = []
    original = _m.can_write

    def spy(actor):
        calls.append(actor)
        return original(actor)

    monkeypatch.setattr(_m, "can_write", spy)
    admin = Actor("admin", "admin", grade=AdminRole.EDITOR)
    can_edit(_record(), admin)
    assert calls == [admin], "can_edit admin 分支應透過 can_write(actor) 判斷，而非重寫字面條件"
