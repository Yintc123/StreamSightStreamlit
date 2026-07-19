"""系統管理頁（Phase 1 Mock）。

薄頁面：兩分頁（日誌 / DB 狀態）。管理員管理已由主前端實作。
"""
import streamlit as st

from lib.auth import require_auth
from lib.config import get_settings
from lib.errors import render_error
from lib.system_management import (
    color_log_level,
    fetch_infra_snapshot,
    format_percent,
    seed_db_status,
    seed_logs,
)
from lib.ui import Metric, empty_state, filter_bar, metric_cards, pagination_controls

require_auth()
settings = get_settings()

DB_STATUS_REFRESH_SECONDS = 1.0

# ── 頁面主体 ─────────────────────────────────────────────────────
st.title("系統管理")

logs_tab, db_tab = st.tabs(["日誌", "DB 狀態"])

# ── 日誌分頁 ─────────────────────────────────────────────────────
with logs_tab:
    logs = seed_logs()

    fp_log = filter_bar(
        categories=["全部", "INFO", "WARNING", "ERROR"],
        key_prefix="admin_log",
        show_keyword=False,
    )

    filtered_logs = logs
    if fp_log.category != "全部":
        filtered_logs = [lg for lg in filtered_logs if lg["level"] == fp_log.category]
    if fp_log.date_from and fp_log.date_to:
        filtered_logs = [
            lg for lg in filtered_logs
            if str(fp_log.date_from) <= lg["time"][:10] <= str(fp_log.date_to)
        ]

    log_total = len(filtered_logs)
    log_size = 50

    if not filtered_logs:
        empty_state("無符合條件的日誌")
    else:
        header = st.columns([2, 2, 3, 3, 2])
        for col, label in zip(header, ["時間", "使用者", "動作", "結果", "等級"]):
            col.caption(label)
        st.divider()
        log_page = st.session_state.get("admin_log_page", 1)
        start = (log_page - 1) * log_size
        for lg in filtered_logs[start:start + log_size]:
            color = color_log_level(lg["level"])
            cols = st.columns([2, 2, 3, 3, 2])
            cols[0].write(lg["time"])
            cols[1].write(lg["user"])
            cols[2].write(lg["action"])
            cols[3].write(lg["result"])
            cols[4].markdown(
                f'<span style="color:{color}">**{lg["level"]}**</span>',
                unsafe_allow_html=True,
            )

    pagination_controls(log_total, log_size, key_prefix="admin_log")

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

