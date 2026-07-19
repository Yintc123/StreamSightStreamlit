"""MockDataSource:記憶體假資料,實作 DataSource 介面。

見規格 docs/specs/data-source.md。種子為 40 筆決定性 Record（固定 seed 隨機值），
平均分佈四分類、跨 alice/bob/admin、跨時間,讓分頁 / 篩選 / 排序 / 圖表看得出效果。
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from lib.models import (
    BULK_MAX_ROWS,
    CATEGORIES,
    DEFAULT_SORT,
    SORTABLE,
    Actor,
    ImportResult,
    Page,
    PermissionDenied,
    Record,
    RecordNotFound,
    RowError,
    ValidationError,
    can_edit,
)

# 固定基準日，往回 90 天（≈3 個月）均勻分佈 200 筆，避免 datetime.now()
_SEED_BASE = datetime(2026, 7, 18, 0, 0, 0, tzinfo=timezone.utc)
_SEED_USERS = ["alice", "bob", "admin"]
_SEED_COUNT = 200
_SPAN_DAYS = 90
_STEP_MINUTES = (_SPAN_DAYS * 24 * 60) // (_SEED_COUNT - 1)  # ≈ 651 min/筆


def make_seed_records() -> List[Record]:
    """產生 200 筆決定性種子（固定 seed 隨機值 10–999，時間跨度 90 天）。"""
    rng = random.Random(2026)
    records: List[Record] = []
    for i in range(_SEED_COUNT):
        category = CATEGORIES[i % len(CATEGORIES)]
        created_by = _SEED_USERS[i % len(_SEED_USERS)]
        created = _SEED_BASE - timedelta(minutes=i * _STEP_MINUTES)
        records.append(
            Record(
                id=i + 1,
                title=f"{category}-{i + 1:03d}",
                value=round(rng.uniform(10.0, 999.0), 1),
                category=category,
                created_by=created_by,
                created_at=created,
                updated_at=created,
            )
        )
    return records


class MockDataSource:
    def __init__(self, records: Optional[List[Record]] = None) -> None:
        # 參照語意:直接操作傳入清單,使 app 經 session_state["mock_records"] 的
        # 建立 / 更新 / 刪除跨 rerun 持久;未傳入則以決定性種子起始。
        self._records: List[Record] = (
            records if records is not None else make_seed_records()
        )

    def list_records(
        self,
        page: int = 1,
        size: int = 20,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        sort: str = DEFAULT_SORT,
        include_deleted: bool = False,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Page:
        rows = self._records
        if not include_deleted:
            rows = [r for r in rows if r.deleted_at is None]
        if category is not None:
            rows = [r for r in rows if r.category == category]
        if keyword:  # 空字串視同無篩選
            kw = keyword.lower()
            rows = [r for r in rows if kw in r.title.lower()]
        if date_from is not None:
            rows = [r for r in rows if r.created_at.date() >= date_from]
        if date_to is not None:
            rows = [r for r in rows if r.created_at.date() <= date_to]
        rows = self._sorted(rows, sort)
        total = len(rows)
        start = (page - 1) * size
        items = rows[start : start + size]
        return Page(items=items, total=total, page=page, size=size)

    def create_record(self, data: dict, actor: Actor) -> Record:
        title, value, category, note = self._validated_fields(data)
        now = datetime.now(timezone.utc)
        new_id = max((r.id for r in self._records), default=0) + 1
        record = Record(
            id=new_id,
            title=title,
            value=value,
            category=category,
            created_by=actor.username,  # 由來源指派,前端不得指定
            created_at=now,
            updated_at=now,
            note=note,
        )
        self._records.append(record)
        return record

    def get_record(self, record_id: int) -> Record:
        return self._require_active(record_id)

    def update_record(self, record_id: int, data: dict, actor: Actor) -> Record:
        record = self._require_active(record_id)
        if not can_edit(record, actor):
            raise PermissionDenied("非創建者且非 Admin,不可更新")
        title, value, category, note = self._validated_fields(data)
        record.title = title
        record.value = value
        record.category = category
        record.note = note
        record.updated_at = datetime.now(timezone.utc)
        return record

    def delete_record(self, record_id: int, actor: Actor) -> None:
        record = self._require_active(record_id)
        if not can_edit(record, actor):
            raise PermissionDenied("非創建者且非 Admin,不可刪除")
        record.deleted_at = datetime.now(timezone.utc)  # 軟刪除

    def bulk_create(self, rows: list, actor: Actor) -> ImportResult:
        if len(rows) > BULK_MAX_ROWS:
            raise ValidationError(f"單檔最多 {BULK_MAX_ROWS} 列,實際 {len(rows)} 列")
        created = 0
        errors: List[RowError] = []
        for index, row in enumerate(rows):  # 逐列驗證,非法不中斷其餘
            try:
                self.create_record(row, actor)
                created += 1
            except ValidationError as exc:
                errors.append(RowError(row_index=index, reason=str(exc)))
        return ImportResult(created=created, errors=errors)

    def _require_active(self, record_id: int) -> Record:
        for record in self._records:
            if record.id == record_id and record.deleted_at is None:
                return record
        raise RecordNotFound(f"找不到記錄 id={record_id}(不存在或已軟刪除)")

    @staticmethod
    def _validated_fields(data: dict):
        """驗證使用者可填欄位(title/value/category/note),回傳正規化值。"""
        title = str(data.get("title", "")).strip()
        if not title:
            raise ValidationError("title 必填且非空")
        category = data.get("category")
        if category not in CATEGORIES:
            raise ValidationError(f"category 不在清單:{category!r}")
        try:
            value = float(data.get("value"))
        except (TypeError, ValueError):
            raise ValidationError("value 需可轉為數值")
        note = str(data.get("note") or "")
        return title, value, category, note

    @staticmethod
    def _sorted(rows: List[Record], sort: str) -> List[Record]:
        field, _, direction = sort.partition(":")
        if field not in SORTABLE:
            raise ValidationError(f"非法排序欄位:{field!r};合法欄位為 {SORTABLE}")
        return sorted(rows, key=lambda r: getattr(r, field), reverse=direction == "desc")
