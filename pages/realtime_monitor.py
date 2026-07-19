"""即時監控頁（單串流）。

支援 use_mock / use_api 兩模式：
  - use_mock=True：sample_value(tick) 每秒決定性生成，不連後端。
  - use_mock=False：RealtimeWsClient 在背景 daemon 執行緒接 FastAPI WebSocket；
    fragment 每秒讀 .buffer / .last_error 快照更新畫面。

版面（由上而下）：靜態標題列 / 說明 / 閾值 slider（fragment 外）→ live_panel（fragment 內，
每秒重繪）：最後更新 caption → 指標卡 → 告警 toast（overlay，不佔版面）→ 折線圖 → 柱狀圖。

見規格 docs/specs/pages/04-realtime-monitor.md 與 04-realtime-ws-client.md。
"""
from datetime import datetime

import streamlit as st

from lib import state as _state
from lib.auth import require_auth
from lib.config import get_settings
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
from lib.realtime_ws import RealtimeWsClient, needs_new_client
from lib.ui import empty_state, metric_cards

require_auth()

settings = get_settings()

# ── 靜態版面（fragment 外，頁面進入時執行一次）──────────────────────────────
st.title("即時監控")
st.caption("模擬即時資料串流（每秒更新）。數值超過閾值時告警。")

st.session_state.setdefault("rt_buffer", [])
st.session_state.setdefault("rt_tick", 0)

if needs_new_client(st.session_state.get("rt_ws_client"), settings.use_mock):
    # st.session_state 只能在主執行緒（ScriptRunContext）安全存取；
    # 在此讀取 token 後以 closure 傳入，背景執行緒不直接碰 session_state。
    # needs_new_client：不存在或已被看門狗停掉（斷線後重回頁面）→ 建新連線並覆蓋舊的。
    _tok = _state.get_token() or ""
    _ws_init = RealtimeWsClient(
        http_base=settings.fastapi_base_url,
        ws_base=settings.fastapi_ws_url,
        get_token=lambda: _tok,
    )
    _ws_init.start()
    st.session_state["rt_ws_client"] = _ws_init

st.slider("告警閾值", 0, 100, int(DEFAULT_THRESHOLD), key="rt_threshold")


@st.fragment(run_every=1.0)
def live_panel() -> None:
    # ── 1) 取 buffer（mock / api 二選一）──────────────────────────────────
    if not settings.use_mock:
        _ws: RealtimeWsClient = st.session_state["rt_ws_client"]
        _ws.touch()   # 心跳：宣告本頁仍在顯示；看門狗據此判定未離開（放在 last_error 判斷前）
        if _ws.last_error:
            st.error(_ws.last_error)
            return   # early return；run_every 繼續，連線恢復後自動切回圖表
        buffer = _ws.buffer
    else:
        buffer = st.session_state["rt_buffer"]

    # ── 2) 渲染──────────────────────────────────────────────────────────
    threshold = st.session_state.get("rt_threshold", int(DEFAULT_THRESHOLD))
    if not buffer:
        empty_state("資料串流啟動中…")
    else:
        st.caption(f"最後更新 {buffer[-1].ts.strftime('%H:%M:%S')}")
        metric_cards(summary_metrics(buffer, threshold))
        if is_over(buffer[-1].value, threshold):
            st.toast(alert_message(buffer[-1].value, threshold), icon="⚠️")
        st.altair_chart(build_chart(buffer, "line"), use_container_width=True)
        st.altair_chart(build_chart(buffer[-RECENT_POINTS:], "bar"), use_container_width=True)

    # ── 3) 生成下一筆餵「下一幀」（mock 專屬）────────────────────────────
    if settings.use_mock:
        tick = st.session_state["rt_tick"]
        reading = Reading(ts=datetime.now().astimezone(), value=sample_value(tick))
        st.session_state["rt_buffer"] = trim(buffer + [reading], MAX_POINTS)
        st.session_state["rt_tick"] = tick + 1


live_panel()
