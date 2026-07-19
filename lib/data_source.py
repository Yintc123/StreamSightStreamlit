"""資料存取介面(Protocol)與工廠。

見規格 docs/specs/data-source.md。頁面只依賴 DataSource 介面,經 get_data_source()
取得實作:mock → MockDataSource(記憶體);api → ApiDataSource(接 API 階段)。
"""
from __future__ import annotations

import functools
from datetime import date
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
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
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


# ---------------------------------------------------------------------------
# 分析頁資料載入（分頁抓全部 + 快取）
#
# 分析頁需對「篩選範圍內全部」資料做聚合（sum/mean/max/min、趨勢、匯出），
# 只抓前 N 筆會讓統計靜默算錯，故以分頁逐頁抓到 total 為止（不設筆數上限）。
# 常見情況由分析頁預設「最近 N 天」時間區間收斂資料量；大範圍才付較高成本。
# 以 st.cache_data 短 TTL 快取，避免每次 rerun（切分頁、改粒度）重查與重算。
# 見 docs/specs/pages/05-analytics.md §資料。
# ---------------------------------------------------------------------------

ANALYTICS_CACHE_TTL_SECONDS = 60
_ANALYTICS_PAGE_SIZE = 1000


def _fetch_all_records(ds, category, date_from, date_to, page_size=_ANALYTICS_PAGE_SIZE):
    """逐頁呼叫 ds.list_records，累積回傳符合篩選的「全部」Record（不截斷）。"""
    items: list = []
    page = 1
    while True:
        result = ds.list_records(
            page=page,
            size=page_size,
            category=category,
            date_from=date_from,
            date_to=date_to,
        )
        items.extend(result.items)
        if not result.items or len(items) >= result.total:
            break
        page += 1
    return items


@st.cache_data(ttl=ANALYTICS_CACHE_TTL_SECONDS, show_spinner=False)
def load_records_df(category, date_from, date_to):
    """分析頁資料入口：分頁抓全部 → DataFrame（快取於篩選參數，短 TTL）。"""
    from lib.analytics import records_to_df

    ds = get_data_source()
    items = _fetch_all_records(ds, category, date_from, date_to)
    return records_to_df(items)


@st.cache_data(ttl=ANALYTICS_CACHE_TTL_SECONDS, show_spinner=False)
def build_export_bytes(_df, cache_key):
    """由 DataFrame 產生 (excel_bytes, csv_bytes)；快取於 cache_key，避免每次 rerun 重建。

    _df 以底線開頭，st.cache_data 不納入雜湊（避免對整張表雜湊）；快取鍵改由
    cache_key（篩選條件 + 筆數）決定，與 load_records_df 的資料一致。
    """
    from lib.analytics import make_excel_bytes

    export_df = _df.reset_index()
    excel_bytes = make_excel_bytes(export_df)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
    return excel_bytes, csv_bytes
