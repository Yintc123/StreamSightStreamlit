"""資料存取介面(Protocol)與工廠。

見規格 docs/specs/data-source.md。頁面只依賴 DataSource 介面,經 get_data_source()
取得實作:mock → MockDataSource(記憶體);api → ApiDataSource(接 API 階段)。
"""
from __future__ import annotations

from typing import Optional, Protocol

import streamlit as st

from lib.config import get_settings
from lib.mock_data_source import MockDataSource, make_seed_records
from lib.models import Actor, DEFAULT_SORT, ImportResult, Page, Record


class DataSource(Protocol):
    def list_records(
        self,
        page: int = 1,
        size: int = 20,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        sort: str = DEFAULT_SORT,
        include_deleted: bool = False,
    ) -> Page: ...

    def get_record(self, record_id: int) -> Record: ...

    def create_record(self, data: dict, actor: Actor) -> Record: ...

    def update_record(self, record_id: int, data: dict, actor: Actor) -> Record: ...

    def delete_record(self, record_id: int, actor: Actor) -> None: ...

    def bulk_create(self, rows: list, actor: Actor) -> ImportResult: ...


def get_data_source() -> DataSource:
    """依 DATA_SOURCE 旗標回傳資料源實作。"""
    settings = get_settings()
    if settings.data_source == "mock":
        if "mock_records" not in st.session_state:
            st.session_state["mock_records"] = make_seed_records()
        return MockDataSource(st.session_state["mock_records"])
    raise NotImplementedError("DATA_SOURCE=api 需 ApiDataSource(接 API 階段)")
