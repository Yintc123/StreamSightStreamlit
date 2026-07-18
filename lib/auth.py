"""Auth 模組:身分單一出口 resolve_actor,以及對 api_client 的 token 接縫。

見規格 docs/specs/auth.md、docs/specs/auth-flow.md。
控制流(401)：
- introspection 是「拿/換 token」的來源;回 401 一律經 api_client._handle → NotAuthenticated。
- resolve_actor(進站辨識):攔 NotAuthenticated → 清狀態 → 回 None(未登入為正常狀態)。
- refresh_token(業務 reactive refresh):讓 NotAuthenticated 往上拋 → 業務呼叫失敗 → 導向登入。
註:introspection 的 st.cache_data 短 TTL 快取(auth-flow §4.6)為後續強化,本版先不快取。
"""
from __future__ import annotations

from typing import Optional

import httpx
import streamlit as st

from lib import state
from lib.api_client import ApiClient
from lib.config import get_settings
from lib.models import Actor, NotAuthenticated

# mock 種子預設身分(auth §3;供開發切換器覆寫)
_DEFAULT_MOCK_ACTOR = Actor("alice", "user")


def resolve_actor() -> Optional[Actor]:
    """身分單一出口:吸收 mock / bff 差異,app.py 只看回傳值。"""
    settings = get_settings()
    if settings.auth_mode == "mock":
        actor = state.get_actor()
        if actor is None:
            actor = Actor(_DEFAULT_MOCK_ACTOR.username, _DEFAULT_MOCK_ACTOR.role)
            state.set_actor(actor)
        return actor

    # bff:無 cookie → 未登入(不打網路)
    if raw_cookie() is None:
        return None
    try:
        data = _introspect()
    except NotAuthenticated:
        state.clear_auth()  # 進站辨識:未登入為正常狀態,清狀態回 None 導向 gate
        return None
    actor = Actor(data["user"]["name"], map_role(data["role"]))
    state.set_actor(actor)
    state.set_token(data["accessToken"], data["expiresAt"])
    return actor


def map_role(raw) -> str:
    """後端數值 role → 字串;role_admin_value(預設 1)為 admin,其餘 user。"""
    return "admin" if raw == get_settings().role_admin_value else "user"


def get_access_token() -> str:
    """供 api_client 帶 Bearer;取當前 JWT(來源 session_state["access_token"])。"""
    if get_settings().auth_mode == "mock":
        raise RuntimeError("AUTH_MODE=mock 無 token")
    token = state.get_token()
    if token is None:
        raise NotAuthenticated("尚無 access token")
    return token


def refresh_token() -> str:
    """重呼 introspection 換新 token 並回寫;401 時讓 NotAuthenticated 往上拋(reactive refresh)。"""
    if get_settings().auth_mode == "mock":
        raise RuntimeError("AUTH_MODE=mock 無 token")
    data = _introspect()  # 401 → NotAuthenticated 傳播(不在此攔)
    state.set_token(data["accessToken"], data["expiresAt"])
    return data["accessToken"]


def raw_cookie() -> Optional[str]:
    """從 st.context.cookies 取加密 session cookie 原值,供 introspection 轉發。"""
    if get_settings().auth_mode == "mock":
        raise RuntimeError("AUTH_MODE=mock 無 cookie")
    cookies = getattr(st.context, "cookies", None) or {}
    return cookies.get(get_settings().session_cookie_name)


def logout() -> None:
    """登出:mock 僅清狀態;bff 呼叫 BFF logout + 清狀態(try/finally,確保本地一定清)。"""
    if get_settings().auth_mode == "mock":
        state.clear_auth()
        return
    # bff:通知後端 session 失效;無論成功與否都清本地狀態(最佳努力,auth-flow §4.5)
    try:
        _do_logout_bff()
    finally:
        state.clear_auth()


def _do_logout_bff() -> None:
    """POST {BFF}/api/auth/logout(帶 cookie + X-CSRF-Token);auth-flow §4.5、§7.3。"""
    csrf = _fetch_csrf()
    settings = get_settings()
    _make_bff_client().request(
        "POST",
        f"{settings.bff_base_url}{settings.bff_logout_path}",
        auth="cookie",
        extra_headers={"X-CSRF-Token": csrf},
    )


def _fetch_csrf() -> str:
    """GET {BFF}/api/csrf(帶 cookie)→ 回傳 csrfToken 字串;供 _do_logout_bff 使用(auth-flow §7.3)。
    CSRF token 取得方式(introspection 一併 vs /api/csrf)為 TBD(auth-flow §9);此處採後者。
    """
    settings = get_settings()
    body = _make_bff_client().request(
        "GET", f"{settings.bff_base_url}{settings.bff_csrf_path}", auth="cookie"
    )
    return body["csrfToken"]


def _introspect() -> dict:
    """打 BFF GET /api/auth/session(轉發 cookie),回身分 data;401 → NotAuthenticated。"""
    settings = get_settings()
    body = _make_bff_client().request(
        "GET", f"{settings.bff_base_url}{settings.bff_session_path}", auth="cookie"
    )
    return body["data"]


def _make_bff_client() -> ApiClient:
    """建立帶 cookie 轉發的 BFF ApiClient(introspection / CSRF / logout 共用)。"""
    settings = get_settings()
    timeout = httpx.Timeout(
        connect=settings.http_connect_timeout_seconds,
        read=settings.http_read_timeout_seconds,
        write=settings.http_read_timeout_seconds,
        pool=settings.http_connect_timeout_seconds,
    )
    return ApiClient(
        client=httpx.Client(timeout=timeout),
        raw_cookie=raw_cookie,
        cookie_name=settings.session_cookie_name,
    )
