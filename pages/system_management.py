"""系統管理頁（Phase 1 Mock）。

薄頁面：兩分頁（日誌 / DB 狀態）。唯讀頁面，無寫入操作。
"""
import streamlit as st

from lib.system_management import (
    color_log_level,
    format_db_size,
    seed_db_status,
    seed_logs,
)
from lib.ui import Metric, empty_state, filter_bar, metric_cards, pagination_controls

# ── 頁面主體 ─────────────────────────────────────────────────────
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
with db_tab:
    db = seed_db_status()
    db_ok = db["connected"]
    metric_cards([
        Metric("連線狀態", "正常" if db_ok else "異常", delta_color="off" if db_ok else "inverse"),
        Metric("各表列數", db["total_rows"]),
        Metric("DB 大小", format_db_size(db["size_bytes"])),
    ])

    st.subheader("即時資料歷史查詢")
    st.date_input("時間範圍", value=[], key="admin_db_date_range")
    records = db.get("history_records", [])
    if records:
        import pandas as pd
        st.dataframe(pd.DataFrame(records), hide_index=True, use_container_width=True)
    else:
        empty_state("無歷史資料")
