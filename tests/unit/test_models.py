from __future__ import annotations

from datetime import datetime, timezone

from lib.models import Actor, Record, can_edit, can_write


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


# --- can_edit(data-source §權限純函式、§落地順序 1) ---

def test_can_edit_admin_always_true():
    # Admin 可編輯任何資料(即使非其建立)
    assert can_edit(_record(created_by="bob"), Actor("admin", "admin")) is True


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
    a = Actor("admin", "admin", grade="super_admin")
    assert a.grade == "super_admin"


def test_can_edit_super_admin_true():
    assert can_edit(_record(created_by="bob"), Actor("admin", "admin", grade="super_admin")) is True


def test_can_edit_editor_admin_true():
    assert can_edit(_record(created_by="bob"), Actor("editor", "admin", grade="editor")) is True


def test_can_edit_viewer_admin_false():
    """Viewer admin 唯讀，不可編輯任何資料。"""
    assert can_edit(_record(created_by="bob"), Actor("viewer", "admin", grade="viewer")) is False


def test_can_edit_viewer_admin_own_record_also_false():
    """Viewer admin 即使是自己建立的資料也不可編輯（唯讀限制）。"""
    assert can_edit(_record(created_by="viewer"), Actor("viewer", "admin", grade="viewer")) is False


# --- can_write(actor)：寫入權限單一真相 ---

def test_can_write_super_admin_true():
    assert can_write(Actor("admin", "admin", grade="super_admin")) is True


def test_can_write_editor_true():
    assert can_write(Actor("editor", "admin", grade="editor")) is True


def test_can_write_viewer_false():
    assert can_write(Actor("viewer", "admin", grade="viewer")) is False


def test_can_write_user_role_false():
    """role='user' → False（latent 防線）。"""
    assert can_write(Actor("alice", "user")) is False


def test_can_write_none_grade_admin_true():
    """grade=None + admin → None != 'viewer' → 可寫（寬鬆預設）。"""
    assert can_write(Actor("admin", "admin", grade=None)) is True
