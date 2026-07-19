"""pages/analytics.py 頁面行為 AppTest。

見規格 docs/specs/pages/05-analytics.md §可測試性/TDD（測試 7–11）。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from lib.api_client import ApiError
from lib.models import Actor

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


# 涵蓋種子資料（2026-04 ~ 2026-07-18）的固定區間；因落地預設改為「最近 7 天」
# 相對真實時鐘，需資料的測試一律明確指定區間，確保與掛鐘無關、可重現。
_DATA_RANGE = [date(2026, 4, 1), date(2026, 7, 18)]


def _open_analytics(actor: Actor, seed_state: dict | None = None) -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = actor
    for key, value in (seed_state or {}).items():
        at.session_state[key] = value
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
    """mock 有資料（指定涵蓋種子的區間）→ 含 4 個 st.metric（統計指標卡）。"""
    at = _open_analytics(Actor("alice", "user"), seed_state={"an_date_range": _DATA_RANGE})
    assert not at.exception
    assert len(at.metric) >= 4


# 測試 8b：落地預設「最近 7 天」時間區間（不再一次撈全部）
def test_landing_defaults_to_recent_7_day_window():
    at = _open_analytics(Actor("alice", "user"))
    rng = at.session_state["an_date_range"]
    assert isinstance(rng, (list, tuple)) and len(rng) == 2
    frm, to = rng
    assert (to - frm).days == 7


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
    import lib.data_source as ds_mod

    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("alice", "user")
    at.run()
    at.switch_page("pages/analytics.py")

    err = ApiError("timeout", request_id="req-test-123")
    ds_mod.load_records_df.clear()  # 使下一次確實查詢，讓 patch 的錯誤生效（非命中快取）
    with patch("lib.mock_data_source.MockDataSource.list_records", side_effect=err):
        at.run()

    assert at.error
    assert any("錯誤代碼" in e.value for e in at.error)
    assert len(at.metric) == 0


# 測試 10b
def test_api_error_empty_state_shown_in_all_tabs():
    """ApiError 時三分頁均顯示 empty_state() 佔位（統計分頁不應為空白）。"""
    import lib.data_source as ds_mod

    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("alice", "user")
    at.run()
    at.switch_page("pages/analytics.py")

    err = ApiError("timeout", request_id="req-test-10b")
    ds_mod.load_records_df.clear()  # 同上：跳過快取，讓 patch 的錯誤實際發生
    with patch("lib.mock_data_source.MockDataSource.list_records", side_effect=err):
        at.run()

    empty_infos = [i for i in at.info if i.value == "目前沒有符合條件的資料"]
    assert len(empty_infos) == 3


# 測試 11
def test_trend_tab_has_granularity_radio():
    """趨勢分頁含粒度選擇 radio（時/日/週）。"""
    at = _open_analytics(Actor("alice", "user"), seed_state={"an_date_range": _DATA_RANGE})
    assert not at.exception
    radios = [r for r in at.radio if r.label == "粒度"]
    assert radios
    assert list(radios[0].options) == ["時", "日", "週"]


# 測試 12
def test_analytics_passes_date_params_to_list_records():
    """分析頁設定日期篩選 → list_records 被傳入 date_from / date_to（server-side 篩選）。"""
    from datetime import date
    from lib.mock_data_source import MockDataSource

    at = _open_analytics(Actor("alice", "user"))
    at.session_state["an_date_range"] = (date(2026, 6, 1), date(2026, 6, 30))

    calls = []
    orig = MockDataSource.list_records

    def spy(self, *args, **kwargs):
        calls.append(kwargs)
        return orig(self, *args, **kwargs)

    with patch("lib.mock_data_source.MockDataSource.list_records", spy):
        at.run()

    assert calls, "list_records 未被呼叫"
    assert calls[0].get("date_from") == date(2026, 6, 1), "date_from 未傳給 list_records"
    assert calls[0].get("date_to") == date(2026, 6, 30), "date_to 未傳給 list_records"


# 測試 13
def test_landing_default_window_passed_to_list_records():
    """落地未手動篩選 → list_records 收到「最近 7 天」區間（非 None、跨度 7 天）。

    取代舊「帶 None（一次撈全部）」行為：改為預設收斂資料量，見 05-analytics.md。
    """
    import lib.data_source as ds_mod
    from lib.mock_data_source import MockDataSource

    at = _open_analytics(Actor("alice", "user"))

    calls = []
    orig = MockDataSource.list_records

    def spy(self, *args, **kwargs):
        calls.append(kwargs)
        return orig(self, *args, **kwargs)

    ds_mod.load_records_df.clear()  # 跳過落地時已快取的結果，讓 spy 觀察到實際查詢
    with patch("lib.mock_data_source.MockDataSource.list_records", spy):
        at.run()

    assert calls
    date_from, date_to = calls[0].get("date_from"), calls[0].get("date_to")
    assert date_from is not None and date_to is not None
    assert (date_to - date_from).days == 7
