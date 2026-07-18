from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib.models import Actor

# repo root 的 app.py(AppTest.from_file 以呼叫端檔案目錄為基準,故用絕對路徑)
APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


def test_app_runs_and_defaults_to_dashboard():
    """全 mock 下進站:app 無例外,預設落在儀表板(app-skeleton §9、§10 步驟 5)。"""
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    titles = [t.value for t in at.title]
    assert "儀表板" in titles


def test_admin_can_open_admin_page():
    """Admin 有註冊系統管理頁,可導入並看到其內容。"""
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("admin", "admin")
    at.run()
    at.switch_page("pages/admin.py")
    at.run()
    assert not at.exception
    assert "系統管理" in [t.value for t in at.title]


def test_non_admin_cannot_open_admin_page():
    """一般使用者未註冊系統管理頁:嘗試導入被擋,停在預設儀表板(比隱藏更安全)。"""
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("bob", "user")
    at.run()
    at.switch_page("pages/admin.py")
    at.run()
    titles = [t.value for t in at.title]
    assert "系統管理" not in titles
    assert "儀表板" in titles
