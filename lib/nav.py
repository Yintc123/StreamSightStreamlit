"""導覽:依 role 動態組頁清單。

見規格 docs/specs/app-skeleton.md §5。非 Admin 動態不註冊系統管理頁(比隱藏更安全)。
render_dev_switcher / 導向登入 helper 於各自 cycle 補上。
"""
from __future__ import annotations

from typing import List

import streamlit as st

from lib import state
from lib.models import Actor, AdminRole

# 開發用切換器選項(僅 mock;換真實 API 後移除)。見 data-source §開發用切換器。
# grade 為 AdminRole 數值：ROOT=999 / SUPER_ADMIN=100 / EDITOR=50 / VIEWER=0
_DEV_ACTORS = [
    ("Root",        Actor("root",   "admin", grade=AdminRole.ROOT)),
    ("Super Admin", Actor("admin",  "admin", grade=AdminRole.SUPER_ADMIN)),
    ("Editor",      Actor("editor", "admin", grade=AdminRole.EDITOR)),
    ("Viewer",      Actor("viewer", "admin", grade=AdminRole.VIEWER)),
]


def build_pages(actor: Actor) -> List:
    """依 actor.grade 回傳 st.Page 清單；grade >= SUPER_ADMIN（≥100）才追加系統管理頁。"""
    pages = [
        # 資料管理：url_path 明確固定為 /data_management（不靠檔名推導）；
        # 併帶 default=True → Streamlit 以預設頁承接根路徑 / 與未匹配路徑（404）fallback。
        st.Page("pages/data_management.py", title="資料管理", url_path="data_management", default=True),
        st.Page("pages/realtime_monitor.py", title="即時監控"),
        st.Page("pages/analytics.py", title="資料分析", url_path="analytics"),
    ]
    if actor.role == "admin" and (actor.grade or 0) >= AdminRole.SUPER_ADMIN:
        pages.append(st.Page("pages/system_management.py", title="系統管理"))
    return pages


def render_dev_switcher(actor: Actor) -> Actor:
    """側邊欄開發用使用者切換器(僅 AUTH_MODE=mock);回傳當前生效的 Actor 並寫回 session。"""
    labels = [label for label, _ in _DEV_ACTORS]
    current = next(
        (label for label, a in _DEV_ACTORS if a.username == actor.username),
        labels[0],
    )
    choice = st.sidebar.selectbox(
        "目前使用者", labels, index=labels.index(current), key="dev_user"
    )
    chosen = next(a for label, a in _DEV_ACTORS if label == choice)
    state.set_actor(chosen)
    return chosen
