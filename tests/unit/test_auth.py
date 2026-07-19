from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
import streamlit as st

from lib import auth
from lib.api_client import ApiError
from lib.models import Actor, AdminRole, NotAuthenticated


@pytest.fixture
def fake_session(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(st, "session_state", store)
    return store


@pytest.fixture
def bff_mode(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "0")


def _set_cookies(monkeypatch, cookies: dict):
    monkeypatch.setattr(st, "context", SimpleNamespace(cookies=cookies))


_INTROSPECT_OK = {"user": {"name": "alice"}, "role": 1, "adminRole": "editor", "accessToken": "jwt", "expiresAt": 123, "csrfToken": "csrf-tok"}


# --- resolve_actor mock 分支(auth §8 測 1–2;APP_ENV 預設 local → AUTH_MODE=mock) ---

def test_resolve_actor_mock_defaults_alice_and_writes_back(fake_session):
    """mock 預設身分為 alice/admin/grade=100（SUPER_ADMIN）（app-skeleton §4、auth §3）。"""
    a = auth.resolve_actor()
    assert a == Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN)
    assert fake_session["actor"] == a  # 預設寫回 session


def test_resolve_actor_mock_returns_existing_actor(fake_session):
    fake_session["actor"] = Actor("admin", "admin")  # 如切換器選 admin
    assert auth.resolve_actor() == Actor("admin", "admin")


# --- get_access_token mock 分支(auth §8 測 3) ---

def test_get_access_token_mock_raises_runtime_error(fake_session):
    with pytest.raises(RuntimeError):
        auth.get_access_token()


def test_refresh_token_mock_raises_runtime_error(fake_session):
    with pytest.raises(RuntimeError):
        auth.refresh_token()


def test_raw_cookie_mock_raises_runtime_error(fake_session):
    with pytest.raises(RuntimeError):
        auth.raw_cookie()


# --- bff 分支(auth §8 測 4–9)---

def test_map_role_admin_user_and_unknown(bff_mode):
    assert auth.map_role(1) == "admin"
    assert auth.map_role(0) == "user"
    assert auth.map_role(99) == "user"


def test_resolve_actor_bff_no_cookie_returns_none_without_network(bff_mode, fake_session, monkeypatch):
    _set_cookies(monkeypatch, {})
    called = {"n": 0}
    monkeypatch.setattr(auth, "_introspect", lambda: called.__setitem__("n", 1))
    assert auth.resolve_actor() is None
    assert called["n"] == 0  # 無 cookie → 不打網路


def test_resolve_actor_bff_success_sets_actor_and_token(bff_mode, fake_session, monkeypatch):
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})
    monkeypatch.setattr(auth, "_introspect", lambda: _INTROSPECT_OK)
    actor = auth.resolve_actor()
    assert actor == Actor("alice", "admin", grade=AdminRole.EDITOR)
    assert fake_session["access_token"] == "jwt"
    assert fake_session["token_expires_at"] == 123


def test_resolve_actor_bff_admin_role_root_string_maps_to_999(bff_mode, fake_session, monkeypatch):
    """BFF 回傳 adminRole='root'（字串）→ Actor.grade=999（AdminRole.ROOT）。"""
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})
    monkeypatch.setattr(auth, "_introspect", lambda: {
        **_INTROSPECT_OK, "adminRole": "root"
    })
    actor = auth.resolve_actor()
    assert actor.grade == AdminRole.ROOT  # 999


def test_resolve_actor_bff_admin_role_super_admin_string_maps_to_100(bff_mode, fake_session, monkeypatch):
    """BFF 回傳 adminRole='super_admin'（字串）→ Actor.grade=100（AdminRole.SUPER_ADMIN）。"""
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})
    monkeypatch.setattr(auth, "_introspect", lambda: {
        **_INTROSPECT_OK, "adminRole": "super_admin"
    })
    actor = auth.resolve_actor()
    assert actor.grade == AdminRole.SUPER_ADMIN  # 100


def test_resolve_actor_bff_admin_role_viewer_string_maps_to_0(bff_mode, fake_session, monkeypatch):
    """BFF 回傳 adminRole='viewer'（字串）→ Actor.grade=0（AdminRole.VIEWER）。"""
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})
    monkeypatch.setattr(auth, "_introspect", lambda: {
        **_INTROSPECT_OK, "adminRole": "viewer"
    })
    actor = auth.resolve_actor()
    assert actor.grade == AdminRole.VIEWER  # 0


def test_resolve_actor_bff_stores_csrf_token(bff_mode, fake_session, monkeypatch):
    """S4: resolve_actor() bff 200 → session_state["csrf_token"] == "csrf-tok"。"""
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})
    monkeypatch.setattr(auth, "_introspect", lambda: _INTROSPECT_OK)
    auth.resolve_actor()
    assert fake_session["csrf_token"] == "csrf-tok"


def test_resolve_actor_bff_401_returns_none_and_clears(bff_mode, fake_session, monkeypatch):
    fake_session["access_token"] = "old"
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})

    def boom():
        raise NotAuthenticated("session 失效")

    monkeypatch.setattr(auth, "_introspect", boom)
    assert auth.resolve_actor() is None
    assert "access_token" not in fake_session  # 清狀態


def test_refresh_token_bff_success_then_401(bff_mode, fake_session, monkeypatch):
    monkeypatch.setattr(
        auth,
        "_introspect",
        lambda: {"user": {"name": "a"}, "role": 0, "accessToken": "new", "expiresAt": 9},
    )
    assert auth.refresh_token() == "new"
    assert fake_session["access_token"] == "new"

    def boom():
        raise NotAuthenticated("x")

    monkeypatch.setattr(auth, "_introspect", boom)
    with pytest.raises(NotAuthenticated):
        auth.refresh_token()


def test_raw_cookie_bff_reads_context_cookie(bff_mode, fake_session, monkeypatch):
    _set_cookies(monkeypatch, {"streamsight_session": "rawval"})
    assert auth.raw_cookie() == "rawval"
    _set_cookies(monkeypatch, {})
    assert auth.raw_cookie() is None


def test_get_access_token_bff_returns_stored_token(bff_mode, fake_session):
    fake_session["access_token"] = "jwt"
    assert auth.get_access_token() == "jwt"


# --- logout mock 分支 ---

def test_logout_mock_clears_state(fake_session):
    """logout() 在 mock 模式清除 actor / access_token / token_expires_at。"""
    fake_session["actor"] = Actor("alice", "user")
    fake_session["access_token"] = "jwt"
    fake_session["token_expires_at"] = 999
    auth.logout()
    assert "actor" not in fake_session
    assert "access_token" not in fake_session
    assert "token_expires_at" not in fake_session


def test_logout_mock_no_network(fake_session, monkeypatch):
    """mock 模式 logout() 不打任何網路(_introspect 不被呼叫)。"""
    called = {"n": 0}

    def boom():
        called["n"] += 1
        return {}

    monkeypatch.setattr(auth, "_introspect", boom)
    auth.logout()
    assert called["n"] == 0


# --- logout bff 分支 ---

def test_logout_bff_calls_do_logout_and_clears_state(bff_mode, fake_session, monkeypatch):
    """bff logout:呼叫 _do_logout_bff 並清狀態。"""
    fake_session["actor"] = Actor("alice", "user")
    fake_session["access_token"] = "jwt"
    called = {"n": 0}
    monkeypatch.setattr(auth, "_do_logout_bff", lambda: called.__setitem__("n", 1))
    auth.logout()
    assert called["n"] == 1
    assert "actor" not in fake_session
    assert "access_token" not in fake_session


def test_logout_bff_clears_state_even_on_network_error(bff_mode, fake_session, monkeypatch):
    """bff logout:即使 _do_logout_bff 拋錯也清本地狀態(最佳努力)。"""
    fake_session["actor"] = Actor("alice", "user")

    def boom():
        raise ApiError("連線失敗")

    monkeypatch.setattr(auth, "_do_logout_bff", boom)
    with pytest.raises(ApiError):
        auth.logout()
    assert "actor" not in fake_session


def test_do_logout_bff_uses_state_csrf_and_sends_origin(bff_mode, fake_session, monkeypatch):
    """S5: _do_logout_bff 從 state.get_csrf() 取 CSRF token，帶 Origin + X-CSRF-Token POST 到 logout 端點。"""
    _set_cookies(monkeypatch, {"streamsight_session": "rawcookie"})
    fake_session["csrf_token"] = "csrf-tok"
    captured = []

    def router(req):
        captured.append(
            {"method": req.method, "path": req.url.path, "headers": dict(req.headers)}
        )
        return httpx.Response(204)

    _orig_client = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kw: _orig_client(transport=httpx.MockTransport(router))
    )
    auth._do_logout_bff()
    assert len(captured) == 1
    r = captured[0]
    assert r["method"] == "POST"
    assert r["path"] == "/api/auth/logout"
    assert r["headers"].get("x-csrf-token") == "csrf-tok"
    assert r["headers"].get("origin") == "http://localhost:8501"
    assert "rawcookie" in (r["headers"].get("cookie") or "")


def test_do_logout_bff_raises_when_csrf_missing(bff_mode, fake_session, monkeypatch):
    """S5c: state.get_csrf() 為 None → 拋 RuntimeError（防止 resolve_actor 未先呼叫）。"""
    _set_cookies(monkeypatch, {"streamsight_session": "rawcookie"})
    # csrf_token 不存在於 fake_session
    with pytest.raises(RuntimeError):
        auth._do_logout_bff()


# --- require_auth 頁面守衛 ---

def test_require_auth_bff_with_actor_does_not_redirect(bff_mode, fake_session, monkeypatch):
    """bff 模式，session 已有 actor → 直接回傳，不呼叫 st.markdown / st.stop。"""
    from lib.models import Actor
    fake_session["actor"] = Actor("alice", "admin")
    redirected = []
    monkeypatch.setattr(st, "markdown", lambda *a, **k: redirected.append(a))
    monkeypatch.setattr(st, "stop", lambda: redirected.append("stop"))
    auth.require_auth()
    assert redirected == []


def test_require_auth_bff_without_actor_redirects_and_stops(bff_mode, fake_session, monkeypatch):
    """bff 模式，session 無 actor → meta refresh 重導登入頁，並呼叫 st.stop()。"""
    stopped = []
    redirected = []
    monkeypatch.setattr(st, "markdown", lambda html, **k: redirected.append(html))
    monkeypatch.setattr(st, "stop", lambda: stopped.append(True))
    auth.require_auth()
    assert stopped == [True]
    assert any("refresh" in h for h in redirected)


def test_require_auth_mock_always_passes(fake_session, monkeypatch):
    """mock 模式一律通過（actor 可能不在 session，但 mock 不需要 BFF 驗證）。"""
    stopped = []
    monkeypatch.setattr(st, "stop", lambda: stopped.append(True))
    auth.require_auth()
    assert stopped == []


# --- BFF http.Client 連線池（api-client.md §31） ---

def test_bff_http_client_is_shared_across_calls(bff_mode, fake_session, monkeypatch):
    """_make_bff_client() 兩次呼叫的底層 httpx.Client 為同一實例（連線池共用）。"""
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})
    c1 = auth._make_bff_client()
    c2 = auth._make_bff_client()
    assert c1._client is c2._client, "每次 rerun 應重用同一 httpx.Client 實例（連線池）"


# --- introspection 快取(auth-flow §4.6) ---

def test_cached_introspect_is_wrapped_with_cache_data():
    """_cached_introspect は st.cache_data でラップされ .clear() メソッドを持つ��auth-flow §4.6）。"""
    assert hasattr(auth, "_cached_introspect"), "auth に _cached_introspect が必要"
    assert callable(getattr(auth._cached_introspect, "clear", None)), \
        "_cached_introspect は st.cache_data でラップされ .clear() を持つ必要"


def test_introspection_cached_for_same_cookie(bff_mode, monkeypatch, fake_session):
    """同一 cookie では _introspect_raw を1回だけ呼ぶ（auth-flow §4.6）。"""
    auth._cached_introspect.clear()
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})
    call_count = [0]

    def counting_raw():
        call_count[0] += 1
        return _INTROSPECT_OK

    monkeypatch.setattr(auth, "_introspect_raw", counting_raw)
    auth.resolve_actor()
    auth.resolve_actor()
    assert call_count[0] == 1, "同じ cookie では BFF を1回だけ叩く（2回目はキャッシュ）"


def test_introspection_cache_cleared_after_401(bff_mode, monkeypatch, fake_session):
    """401 後にキャッシュがクリアされ、次回は BFF を再呼び出しする（auth-flow §4.6）。"""
    auth._cached_introspect.clear()
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})

    calls = []

    def failing_raw():
        calls.append("called")
        raise NotAuthenticated("session 失効")

    monkeypatch.setattr(auth, "_introspect_raw", failing_raw)

    # 1st call: 401 → resolve_actor clears cache & returns None
    result = auth.resolve_actor()
    assert result is None
    assert len(calls) == 1

    # 2nd call: cache was cleared → _introspect_raw is called again
    auth.resolve_actor()
    assert len(calls) == 2, "キャッシュクリア後は BFF を再び呼ぶ"


def test_introspection_cache_cleared_on_bff_logout(bff_mode, monkeypatch, fake_session):
    """bff logout 後にキャッシュがクリアされる（auth-flow §4.6）。"""
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})
    fake_session["csrf_token"] = "tok"
    auth._cached_introspect.clear()

    calls = [0]

    def counting_raw():
        calls[0] += 1
        return _INTROSPECT_OK

    monkeypatch.setattr(auth, "_introspect_raw", counting_raw)
    monkeypatch.setattr(auth, "_do_logout_bff", lambda: None)

    auth.resolve_actor()  # populates cache
    assert calls[0] == 1

    auth.logout()  # should clear cache

    auth.resolve_actor()  # should re-call _introspect_raw
    assert calls[0] == 2, "logout 後はキャッシュがクリアされ BFF を再び呼ぶ"
