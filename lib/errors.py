"""錯誤呈現:例外 → (層級 / 文案 / request_id)的單一實作。

見規格 docs/specs/error-handling.md §3(呈現契約唯一權威)、§5。
to_user_message 為純函式(不碰 Streamlit);render_error 為薄 UI 綁定。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal  # type: ignore

import streamlit as st

from lib import state
from lib.api_client import ApiError
from lib.models import NotAuthenticated, PermissionDenied, RecordNotFound, ValidationError

Level = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class ErrorView:
    level: Level
    text: str
    request_id: Optional[str] = None
    code: Optional[str] = None


def to_user_message(exc: Exception) -> ErrorView:
    """把被攔到的例外翻成 §3 的呈現契約。純函式,不碰 Streamlit。
    NotAuthenticated 不產生 ErrorView——直接 re-raise，由 app.py 處理導向。
    """
    if isinstance(exc, NotAuthenticated):
        raise exc
    if isinstance(exc, ValidationError):
        return ErrorView("error", f"欄位不合法:{exc}")
    if isinstance(exc, PermissionDenied):
        return ErrorView("error", "你沒有權限執行此操作")
    if isinstance(exc, RecordNotFound):
        return ErrorView("warning", "資料不存在或已被移除")
    if isinstance(exc, ApiError):
        rid = exc.request_id
        base = (
            "暫時無法連線,請稍後重試。"
            if exc.status is None
            else "操作失敗,請稍後再試。"
        )
        text = f"{base}錯誤代碼:{rid}" if rid else base
        return ErrorView("error", text, request_id=rid, code=exc.code)
    # fallback(§6):未知例外退回通用文案,不揭露技術細節
    return ErrorView("error", "發生未預期的錯誤,請稍後再試。")


def render_error(exc: Exception) -> None:
    """薄 UI 綁定:依 level 呼 st.error/warning/info;ApiError 類寫 last_request_id。
    NotAuthenticated 直接 re-raise，由 app.py 清 session 後重導登入。
    """
    if isinstance(exc, NotAuthenticated):
        raise exc
    view = to_user_message(exc)
    if view.request_id:
        state.set_last_request_id(view.request_id)
    {"error": st.error, "warning": st.warning, "info": st.info}[view.level](view.text)
