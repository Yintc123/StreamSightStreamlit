from __future__ import annotations

from datetime import datetime, timezone

from lib.models import Actor, Record, can_edit


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
