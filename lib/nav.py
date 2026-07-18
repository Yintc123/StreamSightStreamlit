"""導覽:依 role 動態組頁清單。

見規格 docs/specs/app-skeleton.md §5。非 Admin 動態不註冊系統管理頁(比隱藏更安全)。
render_dev_switcher / 導向登入 helper 於各自 cycle 補上。
"""
from __future__ import annotations

from typing import List

import streamlit as st


def build_pages(role: str) -> List:
    """依角色回傳 st.Page 清單;僅 admin 追加系統管理頁。"""
    pages = [
        st.Page("pages/dashboard.py", title="儀表板", default=True),
        st.Page("pages/data_management.py", title="資料管理"),
        st.Page("pages/realtime_monitor.py", title="即時監控"),
        st.Page("pages/analytics.py", title="資料分析"),
    ]
    if role == "admin":
        pages.append(st.Page("pages/admin.py", title="系統管理"))
    return pages
