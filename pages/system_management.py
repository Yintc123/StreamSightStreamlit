"""系統管理頁。

薄頁面：兩分頁（日誌 / DB 狀態）。管理員管理已由主前端實作。
日誌接後端 GET /monitoring/logs（cursor 分頁）；DB 狀態接 GET /monitoring/infra。
"""
import streamlit as st

from lib.auth import require_auth
from lib.config import get_settings
from lib.errors import render_error
from lib.models import LogsPage
from lib.system_management import (
    date_range_to_ms,
    fetch_infra_snapshot,
    format_percent,
    log_entries_to_rows,
    seed_db_status,
    seed_logs,
)
from lib.ui import Metric, empty_state, filter_bar, metric_cards

require_auth()
settings = get_settings()

DB_STATUS_REFRESH_SECONDS = 1.0

# ── 頁面主体 ─────────────────────────────────────────────────────
st.title("系統管理")

logs_tab, db_tab = st.tabs(["日誌", "DB 狀態"])

# ── 日誌分頁 ─────────────────────────────────────────────────────
with logs_tab:
    fp_log = filter_bar(
        categories=["全部", "INFO", "WARNING", "ERROR"],
        key_prefix="admin_log",
        show_keyword=False,
    )

    # 篩選改變 → 重設游標與棧（避免舊 cursor 與新篩選混用）
    filter_sig = (fp_log.category, fp_log.date_from, fp_log.date_to)
    if st.session_state.get("admin_log_filter_sig") != filter_sig:
        st.session_state["admin_log_filter_sig"] = filter_sig
        st.session_state["admin_log_cursor"] = None
        st.session_state["admin_log_cursor_stack"] = []
    cursor = st.session_state.get("admin_log_cursor")
    cursor_stack = st.session_state.setdefault("admin_log_cursor_stack", [])

    since_ms = until_ms = None
    if fp_log.date_from and fp_log.date_to:
        since_ms, until_ms = date_range_to_ms(fp_log.date_from, fp_log.date_to)

    if settings.use_mock:
        entries = seed_logs()
        if fp_log.category != "全部":
            entries = [e for e in entries if e.level == fp_log.category]
        if since_ms is not None:
            entries = [e for e in entries if since_ms <= e.ts <= until_ms]
        log_page = LogsPage(items=entries, next_cursor=None)
    else:
        from lib.api_client import ApiDataSource
        from lib.data_source import _get_api_client

        try:
            log_page = ApiDataSource(
                _get_api_client(), settings.fastapi_base_url
            ).get_logs(
                level=None if fp_log.category == "全部" else fp_log.category,
                since_ms=since_ms,
                until_ms=until_ms,
                cursor=cursor,
                limit=100,
            )
        except Exception as exc:
            render_error(exc)
            log_page = None

    if log_page is None:
        empty_state("無法載入日誌")
    elif not log_page.items:
        empty_state("無符合條件的日誌")
    else:
        st.caption("時間為 UTC")
        st.dataframe(
            log_entries_to_rows(log_page.items),
            use_container_width=True,
            hide_index=True,
        )

    if log_page is not None:
        col_prev, col_next = st.columns(2)
        with col_prev:
            if st.button(
                "← 上一頁",
                key="admin_log_prev_cursor",
                disabled=not cursor_stack,
            ):
                st.session_state["admin_log_cursor"] = cursor_stack.pop()
                st.rerun()
        with col_next:
            if st.button(
                "下一頁 →",
                key="admin_log_next_cursor",
                disabled=log_page.next_cursor is None,
            ):
                cursor_stack.append(cursor)
                st.session_state["admin_log_cursor"] = log_page.next_cursor
                st.rerun()

# ── DB 狀態分頁 ──────────────────────────────────────────────────
@st.fragment(run_every=DB_STATUS_REFRESH_SECONDS)
def db_status_panel() -> None:
    """每 1 秒局部 rerun：mock 重跑靜態種子；api 重新呼叫 GET /monitoring/infra。"""
    if settings.use_mock:
        db = seed_db_status()
        infra = {
            "cpu_percent":    db["cpu_percent"],
            "memory_percent": db["memory_percent"],
            "db_connections": db["connections"],
        }
    else:
        from lib.data_source import _get_api_client

        try:
            infra = fetch_infra_snapshot(_get_api_client(), settings.fastapi_base_url)
        except Exception as exc:
            render_error(exc)
            return   # early return；run_every 續跑，後端恢復後自動切回指標

    metric_cards([
        Metric("CPU 佔用率", format_percent(infra["cpu_percent"])),
        Metric("記憶體佔用率", format_percent(infra["memory_percent"])),
        Metric(
            "連線數",
            infra["db_connections"] if infra["db_connections"] is not None else "N/A",
        ),
    ])


with db_tab:
    db_status_panel()

