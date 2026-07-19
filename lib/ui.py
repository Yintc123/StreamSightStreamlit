"""共用 UI Helper。

跨頁重複的薄 UI 元件集中於此，供 pages/ 直接呼叫。
純邏輯（_page_caption, _clamp_page）為純函式；st.* 呼叫只作薄包裝。
見規格 docs/specs/ui.md。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil
from typing import List, Optional, Tuple

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


def default_date_range(today: date, days: int) -> Tuple[date, date]:
    """回傳 (today - days, today) 的日期區間，供落地頁預設「最近 N 天」。

    純函式（不依賴系統時鐘）：呼叫端傳入 today，方便單元測試。
    用途見 filter_bar(default_days=...) 與 docs/specs/pages/05-analytics.md。
    """
    return (today - timedelta(days=days), today)


# ---------------------------------------------------------------------------
# UI 元件（薄 Streamlit 包裝）
# ---------------------------------------------------------------------------

def page_shell(name: str) -> "st.delta_generator.DeltaGenerator":
    """回傳每頁最外層的穩定容器（帶「頁面專屬 key」），供路由層 `with` 包住整頁輸出。

    防跨頁殘影（ghosting）：Streamlit 前端對 element tree 做「位置＋型別」的增量
    diff，切頁時同位置、同型別的舊 element 會被就地重用/暫留，直到整輪跑完才修剪，
    使前一頁元件短暫殘留在新頁。給容器一個頁面專屬 key，會讓該區塊有穩定且唯一的
    element 身分（proto.id 編入 `page-<name>`）；切頁時 key 不同 → 整塊 remount
    取代而非同位置重用，藉此消除殘影。見 docs/specs/ui.md、docs/specs/app-skeleton.md。
    """
    return st.container(key=f"page-{name}")


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
    default_days: Optional[int] = None,
) -> FilterParams:
    """篩選列 UI；回傳本次 rerun 的 FilterParams 快照。

    session_state keys（以 key_prefix 為 namespace）：
      {prefix}_category, {prefix}_keyword, {prefix}_date_from, {prefix}_date_to

    default_days（僅在 show_date=True 時有效）：落地頁預設帶「最近 N 天」時間
    區間，避免一次撈全部造成延遲（見 05-analytics.md）。只作首次落地預設
    （setdefault），使用者仍可清空或改選；None → 維持原本「不預設（全部）」。
    """
    cat_key = f"{key_prefix}_category"
    kw_key = f"{key_prefix}_keyword"
    df_key = f"{key_prefix}_date_from"
    dt_key = f"{key_prefix}_date_to"
    range_key = f"{key_prefix}_date_range"

    st.session_state.setdefault(cat_key, categories[0])
    st.session_state.setdefault(kw_key, "")
    st.session_state.setdefault(df_key, None)
    st.session_state.setdefault(dt_key, None)
    if show_date and default_days is not None:
        # 首次落地才植入預設區間；日期 widget 綁定 range_key，session 已有值時
        # st.date_input 的 value= 會被忽略，故以 setdefault 尊重使用者後續調整。
        st.session_state.setdefault(
            range_key, list(default_date_range(date.today(), default_days))
        )

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
            # session 已有值（setdefault 植入或 widget 既有狀態）時不得再帶 value=，
            # 否則 Streamlit 會警告 default value 與 Session State API 重複設值；
            # 省略 value 時 range 模式會由 session 值自動推斷。
            if range_key in st.session_state:
                date_range = st.date_input("時間範圍", key=range_key)
            else:
                date_range = st.date_input("時間範圍", value=[], key=range_key)
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
