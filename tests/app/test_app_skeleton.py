from __future__ import annotations

import logging
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from lib.models import Actor, AdminRole

# repo root 的 app.py(AppTest.from_file 以呼叫端檔案目錄為基準,故用絕對路徑)
APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


def _iter_blocks(node):
    """遞迴走訪 AppTest element tree 的所有子節點。"""
    kids = node.children
    if isinstance(kids, dict):
        kids = list(kids.values())
    for c in (kids or []):
        yield c
        if hasattr(c, "children"):
            yield from _iter_blocks(c)


def _block_ids(at):
    """element tree 中所有帶 proto.id 的容器 id 清單。"""
    return [
        getattr(getattr(b, "proto", None), "id", "") or ""
        for b in _iter_blocks(at.main)
    ]


def test_app_runs_and_defaults_to_data_management():
    """全 mock 下進站:app 無例外,預設落在資料管理(/ 與 404 fallback 頁;儀表板已移除;app-skeleton §9、§10 步驟 5)。"""
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    titles = [t.value for t in at.title]
    assert "資料管理" in titles
    assert "儀表板" not in titles


def test_routed_page_wrapped_in_per_page_container():
    """路由層以當前頁 title 為 key 包一層穩定容器 → 頁身分編入 element id，
    切頁時整塊 remount 取代而非同位置重用，消除跨頁殘影（ghosting）。
    (app-skeleton §3 步驟 ⑧、docs/specs/ui.md page_shell)"""
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    assert any("page-資料管理" in i for i in _block_ids(at))  # 預設落地頁被包住


@pytest.mark.parametrize(
    "page_path, title",
    [
        ("pages/data_management.py", "資料管理"),
        ("pages/realtime_monitor.py", "即時監控"),
        ("pages/analytics.py", "資料分析"),
        ("pages/system_management.py", "系統管理"),
    ],
)
def test_every_page_wrapped_in_per_page_container(page_path, title):
    """全部 4 頁皆經路由層 page_shell 包住（單點修正涵蓋所有頁）：切到各頁後
    element tree 含 page-<title> 容器身分。防殘影對每一頁一致生效。"""
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)
    at.run()
    at.switch_page(page_path)
    at.run()
    assert not at.exception
    assert any(f"page-{title}" in i for i in _block_ids(at))


def test_routed_page_container_changes_on_switch():
    """切到資料分析頁：容器身分改為 page-資料分析，舊頁容器不再存在。"""
    at = AppTest.from_file(APP_PATH)
    at.run()
    at.switch_page("pages/analytics.py")
    at.run()
    assert not at.exception
    ids = _block_ids(at)
    assert any("page-資料分析" in i for i in ids)
    assert not any("page-資料管理" in i for i in ids)


def test_super_admin_can_open_admin_page():
    """super_admin のみ系統管理頁が登録され、内容を閲覧できる。"""
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)
    at.run()
    at.switch_page("pages/system_management.py")
    at.run()
    assert not at.exception
    assert "系統管理" in [t.value for t in at.title]


def test_bff_no_actor_redirects_to_login(monkeypatch):
    """bff 模式無 cookie → actor is None → meta refresh 跳轉 Next.js 登入，不顯示任何業務頁。"""
    monkeypatch.setenv("USE_MOCK", "0")
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    titles = [t.value for t in at.title]
    assert "資料管理" not in titles  # 重導時不渲染任何業務頁（含新預設頁資料管理）
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


def test_dev_switcher_present_in_mock_mode():
    """AUTH_MODE=mock：側邊欄有 key='dev_user' 切換器（app-skeleton §3⑤）。"""
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert any(s.key == "dev_user" for s in at.selectbox)


def test_dev_switcher_absent_in_bff_mode(monkeypatch):
    """USE_MOCK=0：未登入時立即 redirect，切換器不出現。"""
    monkeypatch.setenv("USE_MOCK", "0")
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not any(s.key == "dev_user" for s in at.selectbox)


def test_topbar_rendered_in_app():
    """mock 模式下，app 渲染出含 ss-topbar class 的頂列 HTML 區塊（app-skeleton §3）。

    render_topbar 使用 st.markdown(unsafe_allow_html=True)，可由 at.markdown 驗證。
    """
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    markdowns = [m.value for m in at.markdown]
    assert any("ss-topbar" in m for m in markdowns)


def test_topbar_cms_url_always_passed(monkeypatch):
    """mock 模式でも bff_base_url+bff_cms_path の URL が TopBar に渡される。

    USE_MOCK=1（預設）であっても品牌・管理後台連結が '#' に落ちず、
    bff_base_url(localhost:3000)/cms を href に含むことを確認する。
    """
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    markdowns = [m.value for m in at.markdown]
    topbar_html = next(m for m in markdowns if '<div class="ss-topbar">' in m)
    assert "localhost:3000/cms" in topbar_html


# ── 登出接線（logout.md §5.2）────────────────────────────────────────────────

def test_logout_link_present_in_topbar():
    """TopBar HTML 中包含 ?logout=1 連結（mock 模式）。"""
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    topbar_html = next(m.value for m in at.markdown if 'class="ss-topbar"' in m.value)
    assert "?logout=1" in topbar_html


def test_logout_param_calls_logout_in_mock(monkeypatch):
    """mock 模式帶 ?logout=1：auth.logout() 被呼叫；param 清除後正常以預設角色重進。

    - logout() 本身的清狀態行為由 tests/unit/test_auth.py 完整覆蓋，此處只驗證接線。
    - AppTest 限制：app 端 st.query_params.clear() 不會寫回測試端（且內部 rerun
      會重新注入 param），故以 spy 驗證呼叫、手動移除 param 模擬瀏覽器 URL 已更新。
    """
    called = {"n": 0}

    def _spy_logout():
        from lib import state
        called["n"] += 1
        state.clear_auth()

    monkeypatch.setattr("lib.auth.logout", _spy_logout)

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.query_params["logout"] = "1"
    at.run()                                         # 登出 run
    assert not at.exception
    assert called["n"] >= 1                          # 接線生效：logout() 被呼叫

    if "logout" in at.query_params:                  # 模擬 URL param 已被 clear()
        del at.query_params["logout"]
    at.run()
    assert not at.exception
    assert "actor" in at.session_state               # 預設 mock actor 重建
    assert "資料管理" in [t.value for t in at.title]  # 正常進站（預設落地頁）


def test_logout_param_redirects_to_login_in_bff(monkeypatch):
    """bff 模式帶 ?logout=1：呼叫 _do_logout_bff 後 meta refresh 導向登入頁。"""
    monkeypatch.setenv("USE_MOCK", "0")
    monkeypatch.setenv("BFF_BASE_URL", "http://localhost:3000")

    called = {"logout_bff": 0}
    mock_data = {
        "user": {"id": "u_1", "name": "alice"},
        "role": 1,
        "adminRole": "super_admin",
        "accessToken": "tok",
        "expiresAt": 9999999999000,
        "csrfToken": "csrf-abc",
    }
    # patch lib.auth 模組內部函式（resolve_actor / logout 於呼叫時查模組屬性）
    monkeypatch.setattr("lib.auth.raw_cookie", lambda: "cookie-val")
    monkeypatch.setattr("lib.auth._introspect", lambda: mock_data)
    monkeypatch.setattr(
        "lib.auth._do_logout_bff",
        lambda: called.__setitem__("logout_bff", called["logout_bff"] + 1),
    )

    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    at.query_params["logout"] = "1"
    at.run()
    assert not at.exception
    assert called["logout_bff"] == 1
    markdowns = [m.value for m in at.markdown]
    assert any("refresh" in m and "login" in m for m in markdowns)


# ── 閒置逾時（idle-timeout §8.2）──────────────────────────────────────────────

def test_idle_js_injected_into_app(monkeypatch):
    """app 每次 rerun 以 components.html 注入閒置計時器 JS（含冪等清理鉤子）。"""
    import streamlit.components.v1 as components

    htmls = []
    monkeypatch.setattr(components, "html", lambda html, **kw: htmls.append(html))

    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    assert any("__ssIdleCleanup" in h for h in htmls)   # 閒置 JS 已注入
    assert any("?logout=1&reason=idle" in h for h in htmls)


def test_idle_logout_reason_toast_shown_once():
    """閒置登出後，下一輪 rerun 顯示「因閒置」toast，且只顯示一次（讀後即 pop）。"""
    at = AppTest.from_file(APP_PATH)
    at.run()

    at.session_state["_logout_reason"] = "idle"
    at.run()
    assert not at.exception
    assert any("閒置" in t.value for t in at.toast)      # 顯示一次

    at.run()
    assert not any("閒置" in t.value for t in at.toast)   # 已 pop，不再出現


def test_manual_logout_stays_instant_in_bff(monkeypatch):
    """手動登出（?logout=1 無 reason）維持即時跳轉 content=0，不受閒置規格拖慢。"""
    monkeypatch.setenv("USE_MOCK", "0")
    monkeypatch.setenv("BFF_BASE_URL", "http://localhost:3000")
    mock_data = {
        "user": {"id": "u_1", "name": "alice"}, "role": 1, "adminRole": "super_admin",
        "accessToken": "tok", "expiresAt": 9999999999000, "csrfToken": "csrf-abc",
    }
    monkeypatch.setattr("lib.auth.raw_cookie", lambda: "cookie-val")
    monkeypatch.setattr("lib.auth._introspect", lambda: mock_data)
    monkeypatch.setattr("lib.auth._do_logout_bff", lambda: None)

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.query_params["logout"] = "1"
    at.run()
    assert not at.exception
    markdowns = [m.value for m in at.markdown]
    assert any('content="0;' in m and "login" in m for m in markdowns)   # 即時
    assert not any('content="3;' in m for m in markdowns)


def test_idle_logout_uses_interstitial_in_bff(monkeypatch):
    """閒置登出（?logout=1&reason=idle）走過場頁：顯示原因 + 延時 content=3 跳轉。"""
    monkeypatch.setenv("USE_MOCK", "0")
    monkeypatch.setenv("BFF_BASE_URL", "http://localhost:3000")
    mock_data = {
        "user": {"id": "u_1", "name": "alice"}, "role": 1, "adminRole": "super_admin",
        "accessToken": "tok", "expiresAt": 9999999999000, "csrfToken": "csrf-abc",
    }
    monkeypatch.setattr("lib.auth.raw_cookie", lambda: "cookie-val")
    monkeypatch.setattr("lib.auth._introspect", lambda: mock_data)
    monkeypatch.setattr("lib.auth._do_logout_bff", lambda: None)

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.query_params["logout"] = "1"
    at.query_params["reason"] = "idle"
    at.run()
    assert not at.exception
    markdowns = [m.value for m in at.markdown]
    assert any('content="3;' in m and "login" in m for m in markdowns)   # 延時過場
    assert any("閒置" in i.value for i in at.info)                        # 原因提示


def test_idle_logout_reason_whitelist_rejects_injection(monkeypatch):
    """?logout=1&reason=<script>：非白名單 → 走一般登出、不顯示閒置提示、不反射字串。"""
    called = {"n": 0}

    def _spy_logout():
        from lib import state
        called["n"] += 1
        state.clear_auth()

    monkeypatch.setattr("lib.auth.logout", _spy_logout)

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.query_params["logout"] = "1"
    at.query_params["reason"] = "<script>alert(1)</script>"
    at.run()
    assert not at.exception
    assert called["n"] >= 1                                    # 仍登出
    assert not any("閒置" in t.value for t in at.toast)         # 無閒置提示
    assert not any("<script>" in m.value for m in at.markdown)  # 未反射注入字串
