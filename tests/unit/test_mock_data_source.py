from __future__ import annotations

import pytest

from lib.mock_data_source import MockDataSource
from lib.models import (
    CATEGORIES,
    Actor,
    PermissionDenied,
    RecordNotFound,
    ValidationError,
)


# --- 種子 + list_records 分頁(data-source §MockDataSource、§落地順序 2) ---

def test_seed_has_40_records():
    page = MockDataSource().list_records(page=1, size=20)
    assert page.total == 40
    assert len(page.items) == 20
    assert page.page == 1
    assert page.size == 20


def test_pagination_slices_without_overlap():
    ds = MockDataSource()
    p1 = ds.list_records(page=1, size=20)
    p2 = ds.list_records(page=2, size=20)
    assert len(p2.items) == 20
    ids1 = {r.id for r in p1.items}
    ids2 = {r.id for r in p2.items}
    assert ids1.isdisjoint(ids2)  # 兩頁不重疊


def test_seed_spans_all_categories():
    # 40 筆平均分佈於四個分類,讓篩選看得出效果
    items = MockDataSource().list_records(page=1, size=100).items
    seen = {r.category for r in items}
    assert seen == set(CATEGORIES)


def test_default_excludes_soft_deleted():
    from datetime import datetime, timezone

    from lib.models import Record

    now = datetime(2026, 7, 18, tzinfo=timezone.utc)
    recs = [
        Record(1, "a", 1.0, "感測器", "alice", now, now),
        Record(2, "b", 2.0, "系統", "bob", now, now, deleted_at=now),  # 軟刪除
    ]
    page = MockDataSource(recs).list_records(page=1, size=100)
    assert page.total == 1
    assert [r.id for r in page.items] == [1]


# --- 篩選(data-source §落地順序 3) ---

def _recs(*titles_categories):
    from datetime import datetime, timezone

    from lib.models import Record

    now = datetime(2026, 7, 18, tzinfo=timezone.utc)
    return [
        Record(i + 1, title, 1.0, category, "alice", now, now)
        for i, (title, category) in enumerate(titles_categories)
    ]


def test_filter_by_category_exact():
    page = MockDataSource().list_records(page=1, size=100, category="感測器")
    assert page.total == 10  # 40 平均分 4 類
    assert all(r.category == "感測器" for r in page.items)


def test_filter_keyword_case_insensitive_substring():
    ds = MockDataSource(_recs(("Alpha", "感測器"), ("beta", "系統")))
    assert {r.id for r in ds.list_records(keyword="alp", size=100).items} == {1}
    assert {r.id for r in ds.list_records(keyword="BET", size=100).items} == {2}


def test_empty_keyword_is_no_filter():
    assert MockDataSource().list_records(keyword="", size=100).total == 40


# --- 排序(data-source §落地順序 4) ---

def test_sort_by_value_ascending():
    items = MockDataSource().list_records(sort="value:asc", size=100).items
    values = [r.value for r in items]
    assert values == sorted(values)


def test_sort_by_value_descending():
    items = MockDataSource().list_records(sort="value:desc", size=100).items
    values = [r.value for r in items]
    assert values == sorted(values, reverse=True)


def test_invalid_sort_field_raises_validation_error():
    with pytest.raises(ValidationError):
        MockDataSource().list_records(sort="bogus:asc", size=100)


# --- create_record(data-source §落地順序 5) ---

def test_create_record_appends_and_sets_metadata():
    ds = MockDataSource()
    before = ds.list_records(size=100).total
    rec = ds.create_record(
        {"title": "新資料", "value": 5, "category": "系統", "note": "n"},
        Actor("alice", "user"),
    )
    assert rec.created_by == "alice"  # 由來源指派,前端不得指定
    assert rec.id is not None
    assert rec.created_at is not None and rec.updated_at is not None
    assert ds.list_records(size=100).total == before + 1


def test_create_record_empty_title_raises():
    with pytest.raises(ValidationError):
        MockDataSource().create_record(
            {"title": "  ", "value": 1, "category": "系統"}, Actor("a", "user")
        )


def test_create_record_bad_category_raises():
    with pytest.raises(ValidationError):
        MockDataSource().create_record(
            {"title": "x", "value": 1, "category": "不存在"}, Actor("a", "user")
        )


def test_create_record_non_numeric_value_raises():
    with pytest.raises(ValidationError):
        MockDataSource().create_record(
            {"title": "x", "value": "abc", "category": "系統"}, Actor("a", "user")
        )


# --- get / update / delete(data-source §落地順序 6) ---
# 種子 id=1 為 i=0 → created_by = alice


def test_get_record_returns_record():
    assert MockDataSource().get_record(1).id == 1


def test_get_record_missing_raises_not_found():
    with pytest.raises(RecordNotFound):
        MockDataSource().get_record(9999)


def test_update_by_creator_updates_fields_and_timestamp():
    ds = MockDataSource()
    before = ds.get_record(1)
    updated = ds.update_record(
        1, {"title": "改", "value": 9, "category": "網路"}, Actor("alice", "user")
    )
    assert updated.title == "改"
    assert updated.category == "網路"
    assert updated.updated_at >= before.updated_at


def test_update_admin_can_edit_others():
    updated = MockDataSource().update_record(
        1, {"title": "admin改", "value": 1, "category": "網路"}, Actor("admin", "admin")
    )
    assert updated.title == "admin改"


def test_update_without_permission_raises():
    with pytest.raises(PermissionDenied):
        MockDataSource().update_record(
            1, {"title": "x", "value": 1, "category": "網路"}, Actor("bob", "user")
        )


def test_update_missing_raises_not_found():
    with pytest.raises(RecordNotFound):
        MockDataSource().update_record(
            9999, {"title": "x", "value": 1, "category": "網路"}, Actor("admin", "admin")
        )


def test_delete_soft_deletes_and_hides_record():
    ds = MockDataSource()
    ds.delete_record(1, Actor("alice", "user"))
    with pytest.raises(RecordNotFound):
        ds.get_record(1)  # 軟刪後視為不存在
    assert ds.list_records(size=100).total == 39


def test_delete_without_permission_raises():
    with pytest.raises(PermissionDenied):
        MockDataSource().delete_record(1, Actor("bob", "user"))


def test_delete_missing_raises_not_found():
    with pytest.raises(RecordNotFound):
        MockDataSource().delete_record(9999, Actor("admin", "admin"))


# --- bulk_create(data-source §落地順序 7、§匯入驗證規則) ---

def test_bulk_create_valid_and_invalid_rows_do_not_interrupt():
    ds = MockDataSource([])
    rows = [
        {"title": "a", "value": 1, "category": "系統"},  # 合法
        {"title": "", "value": 2, "category": "系統"},  # 非法:title 空
        {"title": "c", "value": 3, "category": "不存在"},  # 非法:category
    ]
    result = ds.bulk_create(rows, Actor("alice", "user"))
    assert result.created == 1
    assert {e.row_index for e in result.errors} == {1, 2}  # 0-based 列序
    assert ds.list_records(size=100).total == 1  # 僅合法列寫入


def test_bulk_create_over_1000_rows_rejected_wholesale():
    rows = [{"title": "a", "value": 1, "category": "系統"}] * 1001
    with pytest.raises(ValidationError):
        MockDataSource([]).bulk_create(rows, Actor("alice", "user"))
