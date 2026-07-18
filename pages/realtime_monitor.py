"""即時監控頁（單串流）。

模擬即時資料串流：每秒生成一決定性隨機值，折線 / 柱狀圖即時更新，數值超過閾值時告警。
對所有登入者開放（無角色 gate；未登入由 app.py 導向 Next.js）。

版面（由上而下）：靜態標題列 / 說明 / 閾值 slider（fragment 外）→ live_panel（fragment 內，
每秒重繪）：最後更新 caption → 指標卡 → 告警 toast（overlay，不佔版面）→ 折線圖 → 柱狀圖。

執行序（render-then-sample，釘死）：先依當前緩衝繪圖，再生成下一筆餵下一幀——使冷啟首幀
empty_state 天然可達且語意正確，並與接後端（WS 非同步填緩衝）架構一致：屆時只移除第 2 段
（改由 WS callback 填 rt_buffer），第 1 段渲染邏輯一字不改。

見規格 docs/specs/pages/04-realtime-monitor.md。
"""
from datetime import datetime

import streamlit as st

from lib.realtime import (
    DEFAULT_THRESHOLD,
    MAX_POINTS,
    RECENT_POINTS,
    Reading,
    alert_message,
    build_chart,
    is_over,
    sample_value,
    summary_metrics,
    trim,
)
from lib.ui import empty_state, metric_cards

# ── 靜態版面（fragment 外，頁面進入時執行一次）──────────────────────────────
st.title("即時監控")
st.caption("模擬即時資料串流（每秒更新）。數值超過閾值時告警。")

# 先於 fragment 之外初始化 session_state，避免首幀讀 rt_buffer / rt_tick 觸發 KeyError。
# rt_threshold 由下方 slider key="rt_threshold" 自動建立，不在此初始化。
st.session_state.setdefault("rt_buffer", [])
st.session_state.setdefault("rt_tick", 0)

st.slider("告警閾值", 0, 100, int(DEFAULT_THRESHOLD), key="rt_threshold")


@st.fragment(run_every=1.0)
def live_panel() -> None:
    # ── 1) 繪圖：依「當前緩衝」渲染（先渲染、後生成）──────────────────────────
    buffer = st.session_state["rt_buffer"]
    threshold = st.session_state.get("rt_threshold", int(DEFAULT_THRESHOLD))
    if not buffer:  # 冷啟首幀＝真正「串流啟動中…」
        empty_state("資料串流啟動中…")
    else:
        st.caption(f"最後更新 {buffer[-1].ts.strftime('%H:%M:%S')}")
        metric_cards(summary_metrics(buffer, threshold))
        if is_over(buffer[-1].value, threshold):
            # 以 toast overlay 告警，不佔版面 → 圖表不因告警出現/消失而位移。
            # 持續性視覺信號由「目前值」指標卡的 inverse delta 承擔（見 summary_metrics）。
            st.toast(alert_message(buffer[-1].value, threshold), icon="⚠️")
        # 用 Altair 明確格式化 x 軸時間刻度（時:分:秒），st.line_chart 無法指定刻度格式。
        st.altair_chart(build_chart(buffer, "line"), use_container_width=True)
        st.altair_chart(build_chart(buffer[-RECENT_POINTS:], "bar"), use_container_width=True)

    # ── 2) 生成下一筆餵「下一幀」：讀 tick → sample → append → tick+=1 ─────────
    #     mock 專屬；接後端後此段由 WS 推送 callback 填 rt_buffer 取代，第 1 段不變。
    tick = st.session_state["rt_tick"]
    reading = Reading(ts=datetime.now().astimezone(), value=sample_value(tick))
    st.session_state["rt_buffer"] = trim(buffer + [reading], MAX_POINTS)
    st.session_state["rt_tick"] = tick + 1  # 首幀 tick=0，之後遞增


live_panel()
