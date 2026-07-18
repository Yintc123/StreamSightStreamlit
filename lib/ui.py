"""共用 UI Helper。

跨頁重複的薄 UI 元件集中於此，供 pages/ 直接呼叫。
純邏輯（_page_caption, _clamp_page）為純函式；st.* 呼叫只作薄包裝。
見規格 docs/specs/ui.md。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import ceil
from typing import List, Optional

try:
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal  # type: ignore

import streamlit as st


# ---------------------------------------------------------------------------
# 型別定義
# ---------------------------------------------------------------------------

@dataclass
class FilterParams:
    """篩選條件快照；純資料，無 UI 依賴，可直接單元測試。"""
    category: str = "全部"
    keyword: str = ""
    date_from: Optional[date] = None
    date_to: Optional[date] = None


@dataclass
class Metric:
    """單一指標卡資料；純資料，可直接單元測試。"""
    label: str
    value: "int | float | str"
    delta: "Optional[int | float | str]" = None
    delta_color: Literal["normal", "inverse", "off"] = "normal"
    help: Optional[str] = None


# ---------------------------------------------------------------------------
# 純函式（供單元測試）
# ---------------------------------------------------------------------------

def _page_caption(page: int, total_pages: int, total: int) -> str:
    """回傳 caption 字串，不依賴 Streamlit，供單元測試。"""
    return f"第 {page} / {total_pages} 頁 · 共 {total} 筆"


def _clamp_page(page: int, total_pages: int) -> int:
    """確保頁碼在 [1, total_pages] 內（資料異動後頁碼可能越界）。"""
    return max(1, min(page, total_pages))


# ---------------------------------------------------------------------------
# UI 元件（薄 Streamlit 包裝）
# ---------------------------------------------------------------------------

def empty_state(message: str = "目前沒有符合條件的資料") -> None:
    """各頁無資料時的一致呈現。"""
    st.info(message)


def metric_cards(metrics: List[Metric]) -> None:
    """依 metrics 長度建立 columns，每欄 st.metric；空 list 靜默。"""
    if not metrics:
        return
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            st.metric(
                label=m.label,
                value=m.value,
                delta=m.delta,
                delta_color=m.delta_color,
                help=m.help,
            )


def pagination_controls(total: int, size: int, key_prefix: str) -> int:
    """上/下頁按鈕 + 頁碼 caption；total==0 靜默；回傳當前頁碼（1-based）。

    前置條件：size >= 1。
    """
    if total == 0:
        return 1
    total_pages = ceil(total / size)
    key = f"{key_prefix}_page"
    st.session_state.setdefault(key, 1)
    st.session_state[key] = _clamp_page(st.session_state[key], total_pages)
    page = st.session_state[key]

    left, mid, right = st.columns([1, 6, 1])
    with left:
        if st.button("‹ 上一頁", key=f"{key_prefix}_prev", disabled=(page == 1)):
            st.session_state[key] -= 1
            st.rerun()
    with mid:
        st.caption(_page_caption(page, total_pages, total))
    with right:
        if st.button("下一頁 ›", key=f"{key_prefix}_next", disabled=(page == total_pages)):
            st.session_state[key] += 1
            st.rerun()
    return st.session_state[key]


def filter_bar(
    categories: List[str],
    key_prefix: str,
    show_date: bool = True,
    show_keyword: bool = True,
) -> FilterParams:
    """篩選列 UI；回傳本次 rerun 的 FilterParams 快照。

    session_state keys（以 key_prefix 為 namespace）：
      {prefix}_category, {prefix}_keyword, {prefix}_date_from, {prefix}_date_to
    """
    cat_key = f"{key_prefix}_category"
    kw_key = f"{key_prefix}_keyword"
    df_key = f"{key_prefix}_date_from"
    dt_key = f"{key_prefix}_date_to"

    st.session_state.setdefault(cat_key, categories[0])
    st.session_state.setdefault(kw_key, "")
    st.session_state.setdefault(df_key, None)
    st.session_state.setdefault(dt_key, None)

    col_count = 1 + (1 if show_date else 0) + (1 if show_keyword else 0)
    cols = st.columns(col_count)
    col_idx = 0

    with cols[col_idx]:
        cat = st.selectbox("分類", categories, key=cat_key)
    col_idx += 1

    date_from: Optional[date] = None
    date_to: Optional[date] = None
    if show_date:
        with cols[col_idx]:
            # st.date_input range 模式只支援單一 key，故使用 {prefix}_date_range 作為
            # widget binding key（內部實作細節）；解析後同步寫入 spec §7 所列的
            # {prefix}_date_from / {prefix}_date_to，供呼叫端讀取 FilterParams 用。
            date_range = st.date_input("時間範圍", value=[], key=f"{key_prefix}_date_range")
        col_idx += 1
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            date_from, date_to = date_range[0], date_range[1]
            st.session_state[df_key] = date_from
            st.session_state[dt_key] = date_to
        else:
            st.session_state[df_key] = None
            st.session_state[dt_key] = None

    keyword = ""
    if show_keyword:
        with cols[col_idx]:
            keyword = st.text_input("關鍵字", key=kw_key)

    return FilterParams(
        category=cat,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )
