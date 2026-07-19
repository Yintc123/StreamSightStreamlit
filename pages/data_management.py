"""資料管理頁（Phase 1 Mock）。

薄頁面：只呼叫 get_data_source() 存取資料，lib/ 負責所有邏輯。
Dialog 使用 session_state trigger pattern（dm_edit_id / dm_delete_id），
確保 AppTest 可測且 dialog 在 rerun 間保持開啟狀態。
"""
import pandas as pd
import streamlit as st

from lib import state
from lib.data_source import get_data_source
from lib.errors import render_error
from lib.import_utils import parse_csv_bytes, parse_json_bytes
from lib.models import CATEGORIES, DEFAULT_SORT, RecordNotFound, ValidationError, can_edit, can_write
from lib.ui import empty_state, pagination_controls

# ── module-level：dialog 函式必須在最頂層定義 ────────────────────
ds = get_data_source()
actor = state.get_actor()
writable = actor is not None and can_write(actor)


@st.dialog("編輯資料")
def _edit_dialog(record_id: int) -> None:
    try:
        record = ds.get_record(record_id)
    except RecordNotFound:
        st.warning("資料不存在或已被移除")
        if st.button("關閉", key="dm_edit_close"):
            del st.session_state["dm_edit_id"]
            st.rerun()
        return

    with st.form("dm_edit"):
        title    = st.text_input("標題", value=record.title, key="dm_edit_title")
        value    = st.number_input("數值", value=record.value, format="%.2f",
                                   key="dm_edit_value")
        category = st.selectbox("分類", CATEGORIES,
                                index=CATEGORIES.index(record.category),
                                key="dm_edit_category")
        note     = st.text_area("備註", value=record.note, key="dm_edit_note")
        submitted = st.form_submit_button("更新")

    if submitted:
        try:
            ds.update_record(
                record_id,
                {"title": title, "value": value, "category": category, "note": note},
                actor,
            )
            del st.session_state["dm_edit_id"]
            st.toast("已更新")
            st.rerun()
        except ValidationError as e:
            st.error(str(e))


@st.dialog("確認刪除")
def _delete_dialog(record_id: int) -> None:
    try:
        record = ds.get_record(record_id)
    except RecordNotFound:
        st.warning("資料不存在或已被移除")
        if st.button("關閉", key="dm_delete_close"):
            del st.session_state["dm_delete_id"]
            st.rerun()
        return

    st.write(f"確定刪除「**{record.title}**」？此操作無法復原。")
    col_confirm, col_cancel = st.columns(2)
    if col_confirm.button("確認刪除", type="primary", use_container_width=True):
        ds.delete_record(record_id, actor)
        del st.session_state["dm_delete_id"]
        st.toast("已刪除")
        st.rerun()
    if col_cancel.button("取消", use_container_width=True):
        del st.session_state["dm_delete_id"]
        st.rerun()


# ── trigger 檢查（每次 rerun 最優先執行）────────────────────────
if "dm_edit_id" in st.session_state:
    _edit_dialog(st.session_state["dm_edit_id"])
if "dm_delete_id" in st.session_state:
    _delete_dialog(st.session_state["dm_delete_id"])

# ── 頁面主體 ─────────────────────────────────────────────────────
st.title("資料管理")

list_tab, create_tab, import_tab = st.tabs(["列表", "新增", "匯入"])

_SORT_OPTIONS = {
    "ID ↑":      "id:asc",
    "ID ↓":      "id:desc",
    "建立時間 ↓": "created_at:desc",
    "建立時間 ↑": "created_at:asc",
    "標題 ↑":    "title:asc",
    "標題 ↓":    "title:desc",
    "數值 ↑":    "value:asc",
    "數值 ↓":    "value:desc",
    "分類 ↑":    "category:asc",
    "分類 ↓":    "category:desc",
}

with list_tab:
    # ── 篩選表單：點「搜尋」才觸發查詢 ───────────────────────────
    st.session_state.setdefault("dm_category", "全部")
    st.session_state.setdefault("dm_keyword", "")
    st.session_state.setdefault("dm_sort", "ID ↑")
    st.session_state.setdefault("dm_size", 20)

    cat_area, sort_area, size_area, form_area = st.columns([2, 2, 1, 3], vertical_alignment="center")
    with cat_area:
        cat_val = st.selectbox("分類", ["全部"] + CATEGORIES, key="dm_category")
    with sort_area:
        sort_label = st.selectbox("排序", list(_SORT_OPTIONS), key="dm_sort")
    with size_area:
        size = st.selectbox("每頁筆數", [20, 50, 100], key="dm_size")
    with form_area:
        with st.form("dm_filter_form"):
            col_kw, col_btn = st.columns([3, 1], vertical_alignment="center")
            with col_kw:
                kw_val = st.text_input("關鍵字", key="dm_keyword")
            with col_btn:
                st.form_submit_button("搜尋", use_container_width=True)

    # 篩選條件改變時重置頁碼
    _prev = st.session_state.get("dm_prev_filter")
    _cur  = (cat_val, kw_val)
    if _prev is not None and _prev != _cur:
        st.session_state["dm_page"] = 1
    st.session_state["dm_prev_filter"] = _cur
    category = None if cat_val == "全部" else cat_val
    page = st.session_state.get("dm_page", 1)

    try:
        result = ds.list_records(
            page=page,
            size=size,
            category=category,
            keyword=kw_val,
            sort=_SORT_OPTIONS[sort_label],
        )
    except Exception as exc:
        render_error(exc)
        result = None

    if result is None:
        pass  # 錯誤已由 render_error 顯示，保留頁框可重試
    elif result.total == 0:
        empty_state("目前範圍內沒有資料")
    else:
        header = st.columns([1, 3, 1, 1, 1, 2, 2, 1, 1], vertical_alignment="bottom")
        header[0].caption("ID")
        header[1].caption("標題")
        header[2].caption("數值")
        header[3].caption("分類")
        header[4].caption("創建者")
        header[5].caption("建立時間")
        header[6].caption("更新時間")
        st.divider()
        for record in result.items:
            col_id, col_title, col_value, col_cat, col_creator, col_created, col_updated, col_edit, col_del = st.columns([1, 3, 1, 1, 1, 2, 2, 1, 1])
            col_id.write(record.id)
            col_title.write(record.title)
            col_value.write(f"{record.value:.2f}")
            col_cat.write(record.category)
            col_creator.write(record.created_by)
            col_created.write(record.created_at.strftime("%Y-%m-%d %H:%M"))
            col_updated.write(record.updated_at.strftime("%Y-%m-%d %H:%M"))
            editable = actor is not None and can_edit(record, actor)
            if col_edit.button("編輯", key=f"dm_edit_{record.id}", disabled=not editable):
                st.session_state["dm_edit_id"] = record.id
                st.rerun()
            if col_del.button("刪除", key=f"dm_delete_{record.id}", disabled=not editable):
                st.session_state["dm_delete_id"] = record.id
                st.rerun()

        pagination_controls(result.total, size, key_prefix="dm")

with create_tab:
    with st.form("dm_create", clear_on_submit=True):
        title    = st.text_input("標題")
        value    = st.number_input("數值", format="%.2f")
        category = st.selectbox("分類", CATEGORIES)
        note     = st.text_area("備註")
        submitted = st.form_submit_button("送出", disabled=not writable)

    if submitted:
        if not title.strip():
            st.error("標題為必填")
        else:
            try:
                ds.create_record(
                    {"title": title, "value": value, "category": category, "note": note},
                    actor,
                )
                st.toast("已新增")
                st.rerun()
            except ValidationError as e:
                st.error(str(e))

with import_tab:
    st.markdown("支援 **CSV**（含表頭）或 **JSON**（物件陣列），單檔最多 1000 列。")
    st.markdown("必填欄位：`title`、`value`、`category`（需為感測器/系統/應用/網路之一）；選填：`note`。")

    uploaded = st.file_uploader(
        "選擇檔案",
        type=["csv", "json"],
        key="dm_import_file",
    )

    if uploaded is not None:
        content = uploaded.read()
        if uploaded.name.endswith(".json"):
            rows, parse_err = parse_json_bytes(content)
        else:
            rows, parse_err = parse_csv_bytes(content)

        if parse_err:
            st.error(parse_err)
        else:
            st.caption(f"預覽：共 {len(rows)} 列")
            if rows:
                st.dataframe(
                    pd.DataFrame(rows[:10]),
                    hide_index=True,
                    use_container_width=True,
                )
                if len(rows) > 10:
                    st.caption(f"（僅顯示前 10 列）")

                if st.button("確認匯入", type="primary", key="dm_import_confirm", disabled=not writable):
                    result = ds.bulk_create(rows, actor)
                    if result.errors:
                        st.warning(
                            f"匯入完成：成功 **{result.created}** 筆，"
                            f"錯誤 **{len(result.errors)}** 筆（錯誤列未建立）。"
                        )
                        st.caption(
                            f"錯誤列：{', '.join(str(e.row_index + 1) for e in result.errors[:5])}"
                            + ("…" if len(result.errors) > 5 else "")
                        )
                    else:
                        st.success(f"匯入完成：成功 **{result.created}** 筆。")
                    st.rerun()
