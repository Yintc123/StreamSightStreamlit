"""Auth 模組:身分單一出口 resolve_actor,以及對 api_client 的 token 接縫。

見規格 docs/specs/auth.md、docs/specs/auth-flow.md。
控制流(401)：
- introspection 是「拿/換 token」的來源;回 401 一律經 api_client._handle → NotAuthenticated。
- resolve_actor(進站辨識):攔 NotAuthenticated → 清狀態 → 回 None(未登入為正常狀態)。
- refresh_token(業務 reactive refresh):讓 NotAuthenticated 往上拋 → 業務呼叫失敗 → 導向登入。
快取策略(auth-flow §4.6):以 _cached_introspect(cookie_value) 包住 BFF 呼叫;
TTL ≈ 30s；401/logout/refresh 後主動呼叫 _cached_introspect.clear()。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import httpx
import streamlit as st

from lib import state
from lib.api_client import ApiClient
from lib.config import get_settings
from lib.models import Actor, AdminRole, NotAuthenticated

# mock 種子預設身分（app-skeleton §4；供開發切換器覆寫）；SUPER_ADMIN(100) 確保初次開啟即可看到所有頁面
_DEFAULT_MOCK_ACTOR = Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN)


def resolve_actor() -> Optional[Actor]:
    """身分單一出口:吸收 mock / bff 差異,app.py 只看回傳值。"""
    settings = get_settings()
    if settings.use_mock:
        actor = state.get_actor()
        if actor is None:
            actor = Actor(_DEFAULT_MOCK_ACTOR.username, _DEFAULT_MOCK_ACTOR.role, grade=_DEFAULT_MOCK_ACTOR.grade)
            state.set_actor(actor)
        return actor

    # bff:無 cookie → 未登入(不打網路)
    if raw_cookie() is None:
        return None
    try:
        data = _introspect()
    except NotAuthenticated:
        _cached_introspect.clear()  # 401:舊快取失效(auth-flow §4.6)
        state.clear_auth()  # 進站辨識:未登入為正常狀態,清狀態回 None 導向 gate
        return None
    actor = Actor(data["user"]["name"], map_role(data["role"]), grade=int(data["grade"]) if data.get("grade") is not None else None)
    state.set_actor(actor)
    state.set_token(data["accessToken"], data["expiresAt"])
    state.set_csrf(data["csrfToken"])
    return actor


def require_auth() -> None:
    """頁面守衛（安全兜底層）：bff 模式下 actor 未設定則重導登入頁並 stop。"""
    if get_settings().use_mock:
        return
    if state.get_actor() is not None:
        return
    _s = get_settings()
    _login_url = f"{_s.bff_base_url}{_s.bff_login_path}"
    st.markdown(
        f'<meta http-equiv="refresh" content="0; url={_login_url}">',
        unsafe_allow_html=True,
    )
    st.stop()


def map_role(raw) -> str:
    """後端數值 role → 字串;role_admin_value(預設 1)為 admin,其餘 user。"""
    return "admin" if raw == get_settings().role_admin_value else "user"


def get_access_token() -> str:
    """供 api_client 帶 Bearer;取當前 JWT(來源 session_state["access_token"])。"""
    if get_settings().use_mock:
        raise RuntimeError("USE_MOCK=true 無 token")
    token = state.get_token()
    if token is None:
        raise NotAuthenticated("尚無 access token")
    return token


def refresh_token() -> str:
    """重呼 introspection 換新 token 並回寫;401 時讓 NotAuthenticated 往上拋(reactive refresh)。"""
    if get_settings().use_mock:
        raise RuntimeError("USE_MOCK=true 無 token")
    _cached_introspect.clear()  # refresh 前清舊快取,確保打到 BFF 取最新 token(auth-flow §4.6)
    data = _introspect()  # 401 → NotAuthenticated 傳播(不在此攔)
    state.set_token(data["accessToken"], data["expiresAt"])
    return data["accessToken"]


def raw_cookie() -> Optional[str]:
    """從 st.context.cookies 取加密 session cookie 原值,供 introspection 轉發。"""
    if get_settings().use_mock:
        raise RuntimeError("USE_MOCK=true 無 cookie")
    cookies = getattr(st.context, "cookies", None) or {}
    return cookies.get(get_settings().session_cookie_name)


def logout() -> None:
    """登出:mock 僅清狀態;bff 呼叫 BFF logout + 清狀態(try/finally,確保本地一定清)。"""
    if get_settings().use_mock:
        state.clear_auth()
        return
    # bff:通知後端 session 失效;無論成功與否都清本地狀態(最佳努力,auth-flow §4.5)
    try:
        _do_logout_bff()
    finally:
        _cached_introspect.clear()  # 登出後清快取(auth-flow §4.6)
        state.clear_auth()


def _do_logout_bff() -> None:
    """POST {BFF}/api/auth/logout(帶 cookie + X-CSRF-Token + Origin);auth-flow §4.5、§7.3、015 §7.1B。"""
    csrf = state.get_csrf()
    if csrf is None:
        raise RuntimeError("no csrf token in session_state; call resolve_actor() first")
    settings = get_settings()
    _make_bff_client().request(
        "POST",
        f"{settings.bff_base_url}{settings.bff_logout_path}",
        auth="cookie",
        extra_headers={"X-CSRF-Token": csrf, "Origin": settings.streamlit_origin},
    )


def _introspect_raw() -> dict:
    """BFF introspection 的純 HTTP 呼叫（無快取）。應透過 _introspect() 使用。"""
    settings = get_settings()
    body = _make_bff_client().request(
        "GET", f"{settings.bff_base_url}{settings.bff_session_path}", auth="cookie"
    )
    return body["data"]


@st.cache_data(ttl=30, show_spinner=False)
def _cached_introspect(raw_cookie_value: str) -> dict:
    """cookie 原值為 cache key；TTL ≈ 30s（config §3.7 introspection_cache_ttl_seconds）。
    auth-flow §4.6：401/logout/refresh 後呼叫 .clear() 主動失效。
    """
    return _introspect_raw()


def _introspect() -> dict:
    """快取版 introspection；cookie 原值作為 cache key，401 → NotAuthenticated 傳播。"""
    cookie = raw_cookie()
    if cookie is None:
        raise RuntimeError("_introspect called without a cookie; check raw_cookie() first")
    return _cached_introspect(cookie)


@lru_cache
def _get_bff_http_client() -> httpx.Client:
    """模組層級共用的 BFF httpx.Client（連線池）；lru_cache 確保整個 process 僅建立一次。"""
    s = get_settings()
    return httpx.Client(
        timeout=httpx.Timeout(
            connect=s.http_connect_timeout_seconds,
            read=s.http_read_timeout_seconds,
            write=s.http_read_timeout_seconds,
            pool=s.http_connect_timeout_seconds,
        )
    )


def _make_bff_client() -> ApiClient:
    """建立帶 cookie 轉發的 BFF ApiClient(introspection / CSRF / logout 共用)。
    底層 httpx.Client 透過 _get_bff_http_client() 共用，避免每次 rerun 重建連線池。
    """
    settings = get_settings()
    return ApiClient(
        client=_get_bff_http_client(),
        raw_cookie=raw_cookie,
        cookie_name=settings.session_cookie_name,
    )
