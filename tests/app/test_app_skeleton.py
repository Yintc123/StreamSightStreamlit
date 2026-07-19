from __future__ import annotations

import logging
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib.models import Actor

# repo root 的 app.py(AppTest.from_file 以呼叫端檔案目錄為基準,故用絕對路徑)
APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


def test_app_runs_and_defaults_to_analytics():
    """全 mock 下進站:app 無例外,預設落在資料分析(儀表板已移除;app-skeleton §9、§10 步驟 5)。"""
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    titles = [t.value for t in at.title]
    assert "資料分析" in titles
    assert "儀表板" not in titles


def test_super_admin_can_open_admin_page():
    """super_admin のみ系統管理頁が登録され、内容を閲覧できる。"""
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("admin", "admin", grade="super_admin")
    at.run()
    at.switch_page("pages/system_management.py")
    at.run()
    assert not at.exception
    assert "系統管理" in [t.value for t in at.title]


def test_bff_no_actor_redirects_to_login(monkeypatch):
    """bff 模式無 cookie → actor is None → meta refresh 跳轉 Next.js 登入，不顯示任何業務頁。"""
    monkeypatch.setenv("AUTH_MODE", "bff")
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    titles = [t.value for t in at.title]
    assert "資料分析" not in titles
    # meta refresh 含 /login 路徑
    markdowns = [m.value for m in at.markdown]
    assert any("/login" in m for m in markdowns)


def test_app_calls_init_logging_on_startup():
    """app.py 啟動時呼叫 init_logging()，streamsight.api logger 掛上 _streamsight filter。
    (request-id §4.2、app-skeleton §3 步驟 ②′)
    """
    logger = logging.getLogger("streamsight.api")
    # 先清除，確保乾淨的測試起點
    logger.filters = [f for f in logger.filters if not getattr(f, "_streamsight", False)]
    assert not any(getattr(f, "_streamsight", False) for f in logger.filters)

    at = AppTest.from_file(APP_PATH)
    at.run()

    assert any(
        getattr(f, "_streamsight", False) for f in logger.filters
    ), "app.py 應在啟動時呼叫 init_logging()"


def test_not_authenticated_during_nav_clears_and_redirects_to_login(monkeypatch):
    """navigation 執行中拋出 NotAuthenticated 時，app.py 清 session 並重導登入（error-handling §3）。"""
    from lib import nav
    from lib.models import NotAuthenticated

    def _raise(_actor):
        raise NotAuthenticated()

    monkeypatch.setattr(nav, "build_pages", _raise)

    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    markdowns = [m.value for m in at.markdown]
    assert any("/login" in m for m in markdowns)


# build_pages 的存取控制邏輯（user 無法取得 admin 頁）已由
# tests/unit/test_nav.py::test_user_has_no_admin_page 覆蓋；
# mock 模式所有 dev actor 均為 admin 型別，AppTest 無法重現 user 情境，故不重複。
