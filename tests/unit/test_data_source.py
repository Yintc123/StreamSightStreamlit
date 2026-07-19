from __future__ import annotations

import pytest
import streamlit as st

from lib.data_source import get_data_source
from lib.mock_data_source import MockDataSource
from lib.models import Actor


@pytest.fixture
def fake_session(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(st, "session_state", store)
    return store


# --- get_data_source 工廠(data-source §注入點、app-skeleton §6) ---

def test_returns_mock_and_seeds_session(fake_session):
    ds = get_data_source()  # APP_ENV 預設 local → DATA_SOURCE=mock
    assert isinstance(ds, MockDataSource)
    assert len(fake_session["mock_records"]) == 200


def test_crud_persists_across_calls_via_session(fake_session):
    get_data_source().create_record(
        {"title": "新", "value": 1, "category": "系統"}, Actor("alice", "user")
    )
    # 下次取得的資料源仍看得到剛建立的資料(共用 session_state["mock_records"])
    assert get_data_source().list_records(size=300).total == 201


def test_api_mode_returns_apidatasource(monkeypatch, fake_session):
    from lib.api_client import ApiDataSource

    monkeypatch.setenv("APP_ENV", "development")  # api / bff
    assert isinstance(get_data_source(), ApiDataSource)


def test_api_datasource_shares_http_client_across_calls(monkeypatch, fake_session):
    # api-client.md §2：整個 process 共用一個 httpx.Client，避免 TCP handshake 成本
    import lib.data_source as ds_mod
    ds_mod._get_api_client.cache_clear()

    monkeypatch.setenv("APP_ENV", "development")
    ds1 = ds_mod.get_data_source()
    ds2 = ds_mod.get_data_source()
    # 兩次取得的 ApiDataSource 必須共用同一個 ApiClient 實例
    assert ds1._c is ds2._c


# --- MockDataSource.list_records 日期篩選(api-records §4.1) ---

def test_mock_list_records_filters_by_date_from():
    """date_from → 只回傳 created_at.date() >= date_from 的記錄。"""
    from datetime import date
    from lib.mock_data_source import MockDataSource, make_seed_records
    ds = MockDataSource(make_seed_records())
    d = date(2026, 7, 1)
    result = ds.list_records(size=300, date_from=d)
    assert result.total > 0
    for r in result.items:
        assert r.created_at.date() >= d


def test_mock_list_records_filters_by_date_to():
    """date_to → 只回傳 created_at.date() <= date_to 的記錄。"""
    from datetime import date
    from lib.mock_data_source import MockDataSource, make_seed_records
    ds = MockDataSource(make_seed_records())
    d = date(2026, 5, 31)
    result = ds.list_records(size=300, date_to=d)
    assert result.total > 0
    for r in result.items:
        assert r.created_at.date() <= d


def test_mock_list_records_no_date_params_returns_all_200():
    """date_from=None, date_to=None → 回傳全部 200 筆種子（回歸）。"""
    from lib.mock_data_source import MockDataSource, make_seed_records
    ds = MockDataSource(make_seed_records())
    assert ds.list_records(size=300).total == 200


# --- 分析頁：分頁抓全部 + 快取（05-analytics §資料） ---

def _make_records(n: int):
    from datetime import datetime, timezone
    from lib.models import Record
    dt = datetime(2026, 7, 1, tzinfo=timezone.utc)
    return [
        Record(id=i + 1, title=f"t{i}", value=1.0, category="系統",
               created_by="a", created_at=dt, updated_at=dt)
        for i in range(n)
    ]


class _CountingDS:
    """分頁回應的假資料源；記錄 list_records 被呼叫次數。"""

    def __init__(self, records):
        self._records = records
        self.calls = 0

    def list_records(self, page=1, size=20, category=None, keyword=None,
                     sort=None, include_deleted=False, date_from=None, date_to=None):
        from lib.models import Page
        self.calls += 1
        start = (page - 1) * size
        return Page(items=self._records[start:start + size],
                    total=len(self._records), page=page, size=size)


def test_fetch_all_records_pages_through_every_record():
    """分頁抓全部：不因單頁 size 上限而截斷，逐頁抓到 total 為止。"""
    import lib.data_source as ds_mod
    ds = _CountingDS(_make_records(5))
    got = ds_mod._fetch_all_records(ds, None, None, None, page_size=2)
    assert len(got) == 5      # 5 筆全數抓回
    assert ds.calls == 3      # 2 + 2 + 1，共三頁


def test_load_records_df_caches_by_filter_params(monkeypatch):
    """同一組篩選參數重複呼叫 → 命中 st.cache_data，不再打資料源。"""
    import lib.data_source as ds_mod
    calls = {"n": 0}

    def fake_get():
        calls["n"] += 1
        return _CountingDS(_make_records(3))

    monkeypatch.setattr(ds_mod, "get_data_source", fake_get)
    ds_mod.load_records_df.clear()
    df1 = ds_mod.load_records_df(None, None, None)
    df2 = ds_mod.load_records_df(None, None, None)
    assert calls["n"] == 1
    assert len(df1) == len(df2) == 3


def test_build_export_bytes_caches_on_key(monkeypatch):
    """同一 cache_key 重複呼叫 → 只實際序列化一次（不每次重建 Excel）。"""
    import lib.analytics as an_mod
    import lib.data_source as ds_mod
    df = an_mod.records_to_df(_make_records(3))
    calls = {"n": 0}
    real = an_mod.make_excel_bytes

    def spy(x):
        calls["n"] += 1
        return real(x)

    monkeypatch.setattr(an_mod, "make_excel_bytes", spy)
    ds_mod.build_export_bytes.clear()
    key = ("全部", None, None, len(df))
    excel1, csv1 = ds_mod.build_export_bytes(df, key)
    excel2, csv2 = ds_mod.build_export_bytes(df, key)
    assert calls["n"] == 1        # 第二次命中快取
    assert excel1 and csv1        # 皆非空 bytes
    assert b"value" in csv1


