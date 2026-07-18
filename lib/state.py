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


def clear_auth() -> None:
    """登出 / 401:清 actor / token / csrf_token。"""
    for key in (_ACTOR, _ACCESS_TOKEN, _TOKEN_EXPIRES_AT, _CSRF_TOKEN):
        st.session_state.pop(key, None)
