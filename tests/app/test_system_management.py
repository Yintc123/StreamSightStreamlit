from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib.models import Actor, AdminRole

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")
PAGE_PATH = "pages/system_management.py"
PAGE_PATH_DIRECT = str(Path(__file__).resolve().parents[2] / "pages" / "system_management.py")


def _stub_get_logs(monkeypatch, log_page=None):
    """api 模式下日誌分頁也會打 API；AppTest 無 token，以 stub 取代 get_logs。"""
    from lib.models import LogsPage

    result = log_page if log_page is not None else LogsPage(items=[], next_cursor=None)
    monkeypatch.setattr(
        "lib.api_client.ApiDataSource.get_logs",
        lambda self, **kwargs: result,
    )


def _open_system_management_api(actor: Actor, monkeypatch, mock_infra: dict) -> AppTest:
    """use_mock=False helper：直接測頁面（不穿越 app.py）、stub fetch_infra_snapshot。"""
    monkeypatch.setenv("USE_MOCK", "false")
    monkeypatch.setattr(
        "lib.system_management.fetch_infra_snapshot",
        lambda *_: mock_infra,
    )
    _stub_get_logs(monkeypatch)
    at = AppTest.from_file(PAGE_PATH_DIRECT)
    at.session_state["actor"] = actor
    at.run()
    return at


def _open_system_management(actor: Actor) -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = actor
    at.run()
    at.switch_page(PAGE_PATH)
    at.run()
    return at


# --- 5 / 7. 僅 super_admin 可見（標題 + 三分頁） ---

def test_page_has_title_and_two_tabs():
    """super_admin 進入 → 頁面含「系統管理」標題且只有兩個分頁（管理員管理已移至主前端）。"""
    at = _open_system_management(Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN))
    assert not at.exception
    assert any("系統管理" in t.value for t in at.title)
    tab_labels = [t.label for t in at.tabs]
    assert "日誌" in tab_labels
    assert "DB 狀態" in tab_labels
    assert "管理員管理" not in tab_labels


# --- 6. DB 狀態分頁含 metric 指標 ---

def test_db_tab_has_metrics():
    """DB 狀態分頁含 metric 元件（CPU 佔用率、記憶體佔用率、連線數）。"""
    at = _open_system_management(Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN))
    assert not at.exception
    metric_labels = [m.label for m in at.metric]
    assert "CPU 佔用率" in metric_labels
    assert "記憶體佔用率" in metric_labels
    assert "連線數" in metric_labels


# --- 7. 日誌分頁有資料 ---

def test_logs_tab_renders_log_entries():
    """日誌分頁渲染種子日誌（無 exception）。"""
    at = _open_system_management(Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN))
    assert not at.exception


# --- 8. 日期篩選不拋 TypeError ---

def test_log_date_filter_works_without_type_error():
    """日誌日期篩選以字串比對執行，不拋 TypeError；
    2025 年無種子日誌 → 空狀態（「無符合條件的日誌」）。
    """
    from datetime import date

    at = _open_system_management(Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN))
    at.session_state["admin_log_date_range"] = (date(2025, 1, 1), date(2025, 12, 31))
    at.run()
    assert not at.exception
    assert any("無符合條件的日誌" in i.value for i in at.info)


# --- 9. api 模式：正常快照 → 三個指標含數值 ---

def test_db_tab_api_shows_metrics_with_values(monkeypatch):
    """use_mock=False → 呼叫 fetch_infra_snapshot，三個指標顯示後端數值。"""
    at = _open_system_management_api(
        Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN),
        monkeypatch,
        {"cpu_percent": 12.5, "memory_percent": 34.5, "db_connections": 7},
    )
    assert not at.exception
    metric_values = {m.label: m.value for m in at.metric}
    assert metric_values.get("CPU 佔用率") == "12.5%"
    assert metric_values.get("記憶體佔用率") == "34.5%"
    assert str(metric_values.get("連線數")) == "7"


# --- 10. api 模式：exporter 未就緒（None）→ 顯示 N/A，不報錯 ---

def test_db_tab_api_shows_na_when_exporter_unavailable(monkeypatch):
    """cpu_percent / db_connections 為 None → 顯示 'N/A'；memory_percent 正常。"""
    at = _open_system_management_api(
        Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN),
        monkeypatch,
        {"cpu_percent": None, "memory_percent": 34.5, "db_connections": None},
    )
    assert not at.exception
    metric_values = {m.label: m.value for m in at.metric}
    assert metric_values.get("CPU 佔用率") == "N/A"
    assert metric_values.get("記憶體佔用率") == "34.5%"
    assert metric_values.get("連線數") == "N/A"


# --- 11. api 模式：API 呼叫失敗 → render_error → st.error ---

def test_db_tab_api_error_shows_error(monkeypatch):
    """fetch_infra_snapshot 拋 ApiError → render_error → st.error 出現。"""
    from lib.api_client import ApiError

    def _raise(*_):
        raise ApiError("連線失敗", status=None)

    monkeypatch.setenv("USE_MOCK", "false")
    monkeypatch.setattr("lib.system_management.fetch_infra_snapshot", _raise)
    _stub_get_logs(monkeypatch)
    at = AppTest.from_file(PAGE_PATH_DIRECT)
    at.session_state["actor"] = Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN)
    at.run()
    assert not at.exception
    assert len(at.error) >= 1


# --- 13. 日誌分頁以 dataframe 呈現 LogEntry 欄位 ---

def test_logs_tab_renders_dataframe_with_log_columns():
    """mock 模式 → 日誌以 st.dataframe 呈現，欄位為 時間/等級/模組/訊息/Request ID。"""
    import pandas as pd

    at = _open_system_management(Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN))
    assert not at.exception
    assert len(at.dataframe) >= 1
    df = pd.DataFrame(at.dataframe[0].value)
    for col in ["時間", "等級", "模組", "訊息", "Request ID"]:
        assert col in df.columns


# --- 14. 「下一頁」在 next_cursor=None 時禁用 ---

def test_logs_next_button_disabled_when_no_next_cursor():
    """mock 模式 next_cursor 恆為 None → 「下一頁」按鈕禁用；「上一頁」棧空也禁用。"""
    at = _open_system_management(Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN))
    assert not at.exception
    next_btn = next(b for b in at.button if b.key == "admin_log_next_cursor")
    prev_btn = next(b for b in at.button if b.key == "admin_log_prev_cursor")
    assert next_btn.proto.disabled is True
    assert prev_btn.proto.disabled is True


# --- 15. 等級篩選 WARNING → 只顯示 WARNING ---

def test_logs_level_filter_shows_only_matching_rows():
    import pandas as pd

    at = _open_system_management(Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN))
    at.session_state["admin_log_category"] = "WARNING"
    at.run()
    assert not at.exception
    df = pd.DataFrame(at.dataframe[0].value)
    assert len(df) >= 1
    assert set(df["等級"]) == {"WARNING"}


# --- 16. 篩選改變 → cursor 重設為 None、棧清空 ---

def test_logs_filter_change_resets_cursor():
    from datetime import date

    at = _open_system_management(Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN))
    at.session_state["admin_log_cursor"] = "stale-cursor"
    at.session_state["admin_log_cursor_stack"] = ["a", "b"]
    at.session_state["admin_log_date_range"] = (date(2024, 1, 1), date(2024, 1, 2))
    at.run()
    assert not at.exception
    assert at.session_state["admin_log_cursor"] is None
    assert at.session_state["admin_log_cursor_stack"] == []


# --- 12. DB 狀態為 fragment 且 run_every=1.0 ---

def test_db_status_panel_is_fragment_with_1s_interval():
    """db_status_panel 以 @st.fragment(run_every=1.0) 包裹（間隔為規格值 1 秒）。

    AppTest 無法快轉時間驗證排程（屬 Streamlit 框架保證）；
    頁面模組 import 即執行 Streamlit 呼叫，故以原始碼字串斷言常數與裝飾器。
    """
    src = Path(PAGE_PATH_DIRECT).read_text(encoding="utf-8")
    assert "DB_STATUS_REFRESH_SECONDS = 1.0" in src
    assert "@st.fragment(run_every=DB_STATUS_REFRESH_SECONDS)" in src


