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


# --- 5. 所有 grade 可讀（標題 + 四分頁） ---

def test_page_has_title_and_four_tabs():
    """任意 grade 進入 → 頁面含「系統管理」標題且含四個分頁。"""
    at = _open_system_management(Actor("alice", "admin", grade="editor"))
    assert not at.exception
    assert any("系統管理" in t.value for t in at.title)
    tab_labels = [t.label for t in at.tabs]
    assert "使用者" in tab_labels
    assert "權限" in tab_labels
    assert "日誌" in tab_labels
    assert "DB 狀態" in tab_labels


def test_viewer_can_read_page():
    """viewer 可進入且頁面正常渲染（無 exception）。"""
    at = _open_system_management(Actor("viewer", "admin", grade="viewer"))
    assert not at.exception
    assert any("系統管理" in t.value for t in at.title)


# --- 6. viewer：寫入按鈕停用 ---

def test_viewer_toggle_buttons_disabled():
    """viewer：使用者分頁的停用/啟用按鈕全部 disabled。"""
    at = _open_system_management(Actor("viewer", "admin", grade="viewer"))
    toggle_btns = [b for b in at.button if b.label in ("停用", "啟用")]
    assert toggle_btns
    assert all(b.disabled for b in toggle_btns)


def test_viewer_change_grade_button_disabled():
    """viewer：權限分頁的「變更權限」按鈕 disabled。"""
    at = _open_system_management(Actor("viewer", "admin", grade="viewer"))
    change_btn = next((b for b in at.button if b.label == "變更權限"), None)
    assert change_btn is not None
    assert change_btn.disabled


# --- 7. editor / super_admin：寫入按鈕啟用 ---

def test_editor_toggle_buttons_enabled():
    """editor：使用者分頁的停用/啟用按鈕未停用。"""
    at = _open_system_management(Actor("bob", "admin", grade="editor"))
    toggle_btns = [b for b in at.button if b.label in ("停用", "啟用")]
    assert toggle_btns
    assert all(not b.disabled for b in toggle_btns)


def test_super_admin_change_grade_button_enabled():
    """super_admin：「變更權限」按鈕未停用。"""
    at = _open_system_management(Actor("alice", "admin", grade="super_admin"))
    change_btn = next((b for b in at.button if b.label == "變更權限"), None)
    assert change_btn is not None
    assert not change_btn.disabled


# --- 8. DB 狀態分頁含 metric 指標 ---

def test_db_tab_has_metrics():
    """DB 狀態分頁含 metric 元件（連線狀態、各表列數、DB 大小）。"""
    at = _open_system_management(Actor("alice", "admin", grade="super_admin"))
    assert not at.exception
    metric_labels = [m.label for m in at.metric]
    assert "連線狀態" in metric_labels
    assert "各表列數" in metric_labels
    assert "DB 大小" in metric_labels


# --- 9. 日誌分頁有資料 ---

def test_logs_tab_renders_log_entries():
    """日誌分頁渲染種子日誌（無 exception）。"""
    at = _open_system_management(Actor("alice", "admin", grade="super_admin"))
    assert not at.exception
