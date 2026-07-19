"""資料分析頁。

以 st.tabs 分三分頁：統計 / 趨勢 / 匯出。
頂部篩選列（時間範圍 + 分類）三分頁共用。
見規格 docs/specs/pages/05-analytics.md。
"""
import pandas as pd
import streamlit as st

from lib.analytics import (
    agg_by_category,
    agg_stats,
    build_export_caption,
    filter_by_date,
    make_excel_bytes,
    records_to_df,
    resample_series,
)
from lib.data_source import get_data_source
from lib.errors import render_error
from lib.models import CATEGORIES
from lib.ui import Metric, empty_state, filter_bar, metric_cards

st.title("資料分析")

fp = filter_bar(
    categories=["全部"] + CATEGORIES,
    key_prefix="an",
    show_keyword=False,
)

# ── 取資料 ───────────────────────────────────────────────────────────────────

df: pd.DataFrame = pd.DataFrame(columns=["value", "category"])
has_error = False

try:
    ds = get_data_source()
    category_param = None if fp.category == "全部" else fp.category
    result = ds.list_records(page=1, size=1000, category=category_param)
    df = records_to_df(result.items)
    df = filter_by_date(df, fp.date_from, fp.date_to)
except Exception as exc:
    render_error(exc)
    has_error = True

has_data = not df.empty

# ── 匯出資料準備（在 tab 外計算，三分頁共用同一份）─────────────────────────

if has_data:
    export_df = df.reset_index()
    excel_bytes = make_excel_bytes(export_df)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
else:
    excel_bytes = b""
    csv_bytes = b""

# ── 三分頁 ──────────────────────────────────────────────────────────────────

tab_stat, tab_trend, tab_export = st.tabs(["統計", "趨勢", "匯出"])

with tab_stat:
    if has_data:
        stats = agg_stats(df)
        metric_cards([
            Metric("總計", int(stats["sum"])),
            Metric("平均", stats["mean"]),
            Metric("最大", stats["max"]),
            Metric("最小", stats["min"]),
        ])
        st.dataframe(agg_by_category(df), use_container_width=True)
    else:
        empty_state()

with tab_trend:
    if has_data:
        granularity = st.radio(
            "粒度",
            ["時", "日", "週"],
            horizontal=True,
            key="an_granularity",
        )
        freq_map = {"時": "h", "日": "D", "週": "W"}
        freq = freq_map[granularity]

        resampled = resample_series(df, freq)
        st.line_chart(resampled, use_container_width=True)

        pivot = (
            df.groupby([pd.Grouper(freq=freq), "category"])["value"]
            .sum()
            .unstack(fill_value=0)
        )
        if not pivot.empty:
            st.line_chart(pivot, use_container_width=True)
    else:
        empty_state()

with tab_export:
    if has_data:
        st.caption(build_export_caption(fp.category, fp.date_from, fp.date_to, len(df)))
    else:
        empty_state()

    st.download_button(
        "⬇ 下載 Excel (.xlsx)",
        data=excel_bytes,
        file_name="analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=not has_data,
    )
    st.download_button(
        "⬇ 下載 CSV",
        data=csv_bytes,
        file_name="analysis.csv",
        mime="text/csv",
        disabled=not has_data,
    )
