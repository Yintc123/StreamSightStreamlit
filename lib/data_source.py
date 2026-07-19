"""資料存取介面(Protocol)與工廠。

見規格 docs/specs/data-source.md。頁面只依賴 DataSource 介面,經 get_data_source()
取得實作:mock → MockDataSource(記憶體);api → ApiDataSource(接 API 階段)。
"""
from __future__ import annotations

import functools
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
    """依 USE_MOCK 旗標回傳資料源實作。"""
    settings = get_settings()
    if settings.use_mock:
        if "mock_records" not in st.session_state:
            st.session_state["mock_records"] = make_seed_records()
        return MockDataSource(st.session_state["mock_records"])
    return _build_api_data_source(settings)


@functools.lru_cache(maxsize=1)
def _get_api_client():
    """Process 生命週期共用一個 ApiClient（api-client.md §2 single shared Client）。"""
    import httpx

    from lib import auth
    from lib.api_client import ApiClient

    settings = get_settings()
    timeout = httpx.Timeout(
        connect=settings.http_connect_timeout_seconds,
        read=settings.http_read_timeout_seconds,
        write=settings.http_read_timeout_seconds,
        pool=settings.http_connect_timeout_seconds,
    )
    return ApiClient(
        client=httpx.Client(timeout=timeout),
        get_token=auth.get_access_token,
        refresh_token=auth.refresh_token,
        raw_cookie=auth.raw_cookie,
        cookie_name=settings.session_cookie_name,
        retry_max=settings.http_retry_max,
        retry_base=settings.http_retry_base_seconds,
        retry_factor=settings.http_retry_factor,
    )


def _build_api_data_source(settings) -> DataSource:
    from lib.api_client import ApiDataSource

    return ApiDataSource(_get_api_client(), settings.fastapi_base_url)
