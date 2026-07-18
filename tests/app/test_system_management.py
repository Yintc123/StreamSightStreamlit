from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib.models import Actor

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")
PAGE_PATH = "pages/system_management.py"


def _open_system_management(actor: Actor) -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = actor
    at.run()
    at.switch_page(PAGE_PATH)
    at.run()
    return at


# --- 5. 所有 grade 可讀（標題 + 兩分頁） ---

def test_page_has_title_and_two_tabs():
    """任意 grade 進入 → 頁面含「系統管理」標題且含兩個分頁。"""
    at = _open_system_management(Actor("alice", "admin", grade="editor"))
    assert not at.exception
    assert any("系統管理" in t.value for t in at.title)
    tab_labels = [t.label for t in at.tabs]
    assert "日誌" in tab_labels
    assert "DB 狀態" in tab_labels
    assert "使用者" not in tab_labels
    assert "權限" not in tab_labels


def test_viewer_can_read_page():
    """viewer 可進入且頁面正常渲染（無 exception）。"""
    at = _open_system_management(Actor("viewer", "admin", grade="viewer"))
    assert not at.exception
    assert any("系統管理" in t.value for t in at.title)


# --- 6. DB 狀態分頁含 metric 指標 ---

def test_db_tab_has_metrics():
    """DB 狀態分頁含 metric 元件（連線狀態、各表列數、DB 大小）。"""
    at = _open_system_management(Actor("alice", "admin", grade="super_admin"))
    assert not at.exception
    metric_labels = [m.label for m in at.metric]
    assert "連線狀態" in metric_labels
    assert "各表列數" in metric_labels
    assert "DB 大小" in metric_labels


# --- 7. 日誌分頁有資料 ---

def test_logs_tab_renders_log_entries():
    """日誌分頁渲染種子日誌（無 exception）。"""
    at = _open_system_management(Actor("alice", "admin", grade="super_admin"))
    assert not at.exception


# --- 8. 日期篩選不拋 TypeError ---

def test_log_date_filter_works_without_type_error():
    """日誌日期篩選以字串比對執行，不拋 TypeError；
    2025 年無種子日誌 → 空狀態（「無符合條件的日誌」）。
    """
    from datetime import date

    at = _open_system_management(Actor("alice", "admin", grade="super_admin"))
    at.session_state["admin_log_date_range"] = (date(2025, 1, 1), date(2025, 12, 31))
    at.run()
    assert not at.exception
    assert any("無符合條件的日誌" in i.value for i in at.info)
