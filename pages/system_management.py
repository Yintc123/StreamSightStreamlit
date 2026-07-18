"""系統管理頁（Phase 1 Mock）。

薄頁面：四分頁（使用者 / 權限 / 日誌 / DB 狀態）。
寫入 gate 依 can_write(actor)；viewer 唯讀，按鈕停用但不隱藏。
Dialog 使用 session_state trigger pattern（admin_perm_pending），與 data_management 一致。
"""
import streamlit as st

from lib import state
from lib.models import can_write
from lib.system_management import (
    color_log_level,
    format_db_size,
    is_last_super_admin,
    seed_db_status,
    seed_logs,
    seed_users,
)
from lib.ui import Metric, empty_state, filter_bar, metric_cards, pagination_controls

# ── module-level：dialog 函式必須在最頂層定義 ────────────────────
actor = state.get_actor()
writable = actor is not None and can_write(actor)


@st.dialog("確認變更權限")
def _perm_dialog(target_username: str, new_grade: str) -> None:
    users = st.session_state.get("admin_users", seed_users())
    st.write(f"確定將 **{target_username}** 的權限變更為 **{new_grade}**？")
    col_confirm, col_cancel = st.columns(2)
    if col_confirm.button("確認", type="primary", use_container_width=True, key="admin_perm_dialog_confirm"):
        if is_last_super_admin(users, target_username) and new_grade != "super_admin":
            st.error("無法移除最後一位 super_admin")
        else:
            for u in users:
                if u["username"] == target_username:
                    u["grade"] = new_grade
                    break
            del st.session_state["admin_perm_pending"]
            st.toast(f"已將 {target_username} 的權限變更為 {new_grade}")
            st.rerun()
    if col_cancel.button("取消", use_container_width=True, key="admin_perm_dialog_cancel"):
        del st.session_state["admin_perm_pending"]
        st.rerun()


# ── trigger 檢查（每次 rerun 最優先執行）────────────────────────
if "admin_perm_pending" in st.session_state:
    p = st.session_state["admin_perm_pending"]
    _perm_dialog(p["username"], p["grade"])

# ── 頁面主體 ─────────────────────────────────────────────────────
st.title("系統管理")

users_tab, perms_tab, logs_tab, db_tab = st.tabs(["使用者", "權限", "日誌", "DB 狀態"])

# ── 使用者分頁 ───────────────────────────────────────────────────
with users_tab:
    st.session_state.setdefault("admin_users", seed_users())
    users = st.session_state["admin_users"]

    fp = filter_bar(
        categories=["全部", "super_admin", "editor", "viewer"],
        key_prefix="admin_user",
        show_date=False,
        show_keyword=True,
    )

    filtered = users
    if fp.category != "全部":
        filtered = [u for u in filtered if u.get("grade") == fp.category]
    if fp.keyword:
        kw = fp.keyword.lower()
        filtered = [u for u in filtered if kw in u["username"].lower() or kw in u["email"].lower()]

    if not filtered:
        empty_state("無符合條件的使用者")
    else:
        header = st.columns([2, 3, 2, 2, 2, 2])
        for col, label in zip(header, ["帳號", "Email", "Grade", "建立時間", "狀態", "操作"]):
            col.caption(label)
        st.divider()
        for u in filtered:
            cols = st.columns([2, 3, 2, 2, 2, 2])
            cols[0].write(u["username"])
            cols[1].write(u["email"])
            cols[2].write(u["grade"])
            cols[3].write(u["created_at"])
            cols[4].write(u["status"])
            is_active = u["status"] == "active"
            btn_label = "停用" if is_active else "啟用"
            if cols[5].button(btn_label, key=f"admin_user_toggle_{u['username']}", disabled=not writable):
                u["status"] = "inactive" if is_active else "active"
                st.toast(f"已{'停用' if u['status'] == 'inactive' else '啟用'} {u['username']}")
                st.rerun()

# ── 權限分頁 ─────────────────────────────────────────────────────
with perms_tab:
    st.session_state.setdefault("admin_users", seed_users())
    users = st.session_state["admin_users"]
    usernames = [u["username"] for u in users]

    target = st.selectbox("選擇使用者", usernames, key="admin_perm_target")
    new_grade = st.radio("新權限", ["super_admin", "editor", "viewer"], key="admin_perm_grade")

    if st.button("變更權限", key="admin_perm_change", disabled=not writable):
        st.session_state["admin_perm_pending"] = {"username": target, "grade": new_grade}
        st.rerun()

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
            if fp_log.date_from <= lg["time"][:10] <= str(fp_log.date_to)
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
        Metric("連線狀態", "正常" if db_ok else "異常"),
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
