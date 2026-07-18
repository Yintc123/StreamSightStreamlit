"""資料管理頁(列表 slice)。

薄頁面:只呼叫 get_data_source() 取資料、依 can_edit 控制逐列按鈕停用。
新增 / 匯入 / 編輯彈窗等分頁於後續 cycle 補上(見 docs/specs/pages/03-data-management.md)。
"""
import pandas as pd
import streamlit as st

from lib import state
from lib.data_source import get_data_source
from lib.models import can_edit

st.title("資料管理")

actor = state.get_actor()
result = get_data_source().list_records(page=1, size=20)

if result.total == 0:
    st.info("目前範圍內沒有資料")
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

    st.caption(f"第 {result.page} 頁 · 共 {result.total} 筆")
