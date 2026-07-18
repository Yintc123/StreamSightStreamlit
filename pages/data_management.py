"""資料管理頁(列表 slice)。

薄頁面:只呼叫 get_data_source() 取資料、依 can_edit 控制逐列按鈕停用。
新增 / 匯入 / 編輯彈窗等分頁於後續 cycle 補上(見 docs/specs/pages/03-data-management.md)。
"""
import pandas as pd
import streamlit as st

from lib import state
from lib.data_source import get_data_source
from lib.models import can_edit
from lib.ui import empty_state, filter_bar, pagination_controls

st.title("資料管理")

_PREV_FILTER_KEY = "dm_prev_filter"

filter_params = filter_bar(["全部", "感測器", "系統", "應用", "網路"], key_prefix="dm")
_prev = st.session_state.get(_PREV_FILTER_KEY)
if _prev is not None and _prev != filter_params:
    st.session_state["dm_page"] = 1
st.session_state[_PREV_FILTER_KEY] = filter_params

actor = state.get_actor()
result = get_data_source().list_records(page=1, size=20)

if result.total == 0:
    empty_state("目前範圍內沒有資料")
else:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "標題": r.title,
                    "數值": r.value,
                    "分類": r.category,
                    "創建者": r.created_by,
                    "建立時間": r.created_at,
                }
                for r in result.items
            ]
        ),
        hide_index=True,
    )

    for record in result.items:
        title_col, edit_col, delete_col = st.columns([4, 1, 1])
        title_col.write(record.title)
        editable = actor is not None and can_edit(record, actor)
        edit_col.button("編輯", key=f"dm_edit_{record.id}", disabled=not editable)
        delete_col.button("刪除", key=f"dm_delete_{record.id}", disabled=not editable)

    pagination_controls(result.total, 20, key_prefix="dm")
