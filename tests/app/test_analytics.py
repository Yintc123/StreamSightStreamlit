"""pages/analytics.py 頁面行為 AppTest。

見規格 docs/specs/pages/05-analytics.md §可測試性/TDD（測試 7–11）。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from lib.api_client import ApiError
from lib.models import Actor

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


def _open_analytics(actor: Actor) -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = actor
    at.run()
    at.switch_page("pages/analytics.py")
    at.run()
    return at


# 測試 7
def test_page_shows_analytics_title():
    """全 mock 下進入分析頁 → 含「資料分析」標題。"""
    at = _open_analytics(Actor("alice", "user"))
    assert not at.exception
    assert any("資料分析" in t.value for t in at.title)


# 測試 8
def test_seed_data_shows_four_metrics():
    """mock 有資料 → 含 4 個 st.metric（統計指標卡）。"""
    at = _open_analytics(Actor("alice", "user"))
    assert not at.exception
    assert len(at.metric) >= 4


# 測試 9
def test_empty_data_shows_info_and_no_metrics():
    """無資料（空記錄集）→ 含 st.info 空狀態，統計指標卡不渲染。
    注：Streamlit 1.50.0 AppTest 不暴露 download_button；
        disabled=not has_data 的邏輯由頁面程式碼保證，透過 unit test 間接覆蓋。
    """
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("alice", "user")
    at.session_state["mock_records"] = []
    at.run()
    at.switch_page("pages/analytics.py")
    at.run()
    assert not at.exception
    assert at.info
    assert len(at.metric) == 0


# 測試 10
def test_api_error_shows_st_error_with_request_id():
    """`list_records` 拋 ApiError → st.error 含「錯誤代碼」，指標卡不渲染。"""
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("alice", "user")
    at.run()
    at.switch_page("pages/analytics.py")

    err = ApiError("timeout", request_id="req-test-123")
    with patch("lib.mock_data_source.MockDataSource.list_records", side_effect=err):
        at.run()

    assert at.error
    assert any("錯誤代碼" in e.value for e in at.error)
    assert len(at.metric) == 0


# 測試 10b
def test_api_error_empty_state_shown_in_all_tabs():
    """ApiError 時三分頁均顯示 empty_state() 佔位（統計分頁不應為空白）。"""
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("alice", "user")
    at.run()
    at.switch_page("pages/analytics.py")

    err = ApiError("timeout", request_id="req-test-10b")
    with patch("lib.mock_data_source.MockDataSource.list_records", side_effect=err):
        at.run()

    empty_infos = [i for i in at.info if i.value == "目前沒有符合條件的資料"]
    assert len(empty_infos) == 3


# 測試 11
def test_trend_tab_has_granularity_radio():
    """趨勢分頁含粒度選擇 radio（時/日/週）。"""
    at = _open_analytics(Actor("alice", "user"))
    assert not at.exception
    radios = [r for r in at.radio if r.label == "粒度"]
    assert radios
    assert list(radios[0].options) == ["時", "日", "週"]
