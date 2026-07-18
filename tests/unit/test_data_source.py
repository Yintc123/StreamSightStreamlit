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


def test_api_plus_mock_combo_raises_at_startup(monkeypatch):
    # §9 測 9:無效組合由 config 守衛在 get_settings() 啟動時擋下
    monkeypatch.setenv("DATA_SOURCE", "api")
    monkeypatch.setenv("AUTH_MODE", "mock")
    with pytest.raises(ValueError):
        get_data_source()
