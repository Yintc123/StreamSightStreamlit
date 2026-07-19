"""session_state 純儲存層:跨頁共用 key 的讀寫 helper。

見規格 docs/specs/app-skeleton.md §7 / §7.1。只讀寫 st.session_state,不含業務邏輯
(role 映射在 auth、呈現在 errors、token 生命週期 refresh 在 auth)。
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from lib.models import Actor

_ACTOR = "actor"
_ACCESS_TOKEN = "access_token"
_TOKEN_EXPIRES_AT = "token_expires_at"
_CSRF_TOKEN = "csrf_token"
_LAST_REQUEST_ID = "last_request_id"
_LOGOUT_REASON = "_logout_reason"


def get_actor() -> Optional[Actor]:
    return st.session_state.get(_ACTOR)


def set_actor(actor: Actor) -> None:
    st.session_state[_ACTOR] = actor


def get_token() -> Optional[str]:
    return st.session_state.get(_ACCESS_TOKEN)


def set_token(token: str, expires_at: int) -> None:
    st.session_state[_ACCESS_TOKEN] = token
    st.session_state[_TOKEN_EXPIRES_AT] = expires_at


def get_csrf() -> Optional[str]:
    return st.session_state.get(_CSRF_TOKEN)


def set_csrf(token: str) -> None:
    st.session_state[_CSRF_TOKEN] = token


def set_last_request_id(rid: Optional[str]) -> None:
    st.session_state[_LAST_REQUEST_ID] = rid


def set_logout_reason(reason: str) -> None:
    """存登出原因(如 'idle'),供下一輪 rerun 顯示提示;跨 clear_auth 存活。"""
    st.session_state[_LOGOUT_REASON] = reason


def pop_logout_reason() -> Optional[str]:
    """讀出並清除登出原因(只顯示一次)。"""
    return st.session_state.pop(_LOGOUT_REASON, None)


def clear_auth() -> None:
    """登出 / 401:清 actor / token / csrf_token(不含 _logout_reason,需跨 rerun 存活)。"""
    for key in (_ACTOR, _ACCESS_TOKEN, _TOKEN_EXPIRES_AT, _CSRF_TOKEN):
        st.session_state.pop(key, None)
