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


def test_bff_no_actor_redirects_to_login(monkeypatch):
    """bff 模式無 cookie → actor is None → meta refresh 跳轉 Next.js 登入，不顯示儀表板。"""
    monkeypatch.setenv("AUTH_MODE", "bff")
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    titles = [t.value for t in at.title]
    assert "儀表板" not in titles
    # meta refresh 含 /login 路徑
    markdowns = [m.value for m in at.markdown]
    assert any("/login" in m for m in markdowns)


# build_pages 的存取控制邏輯（user 無法取得 admin 頁）已由
# tests/unit/test_nav.py::test_user_has_no_admin_page 覆蓋；
# mock 模式所有 dev actor 均為 admin 型別，AppTest 無法重現 user 情境，故不重複。
