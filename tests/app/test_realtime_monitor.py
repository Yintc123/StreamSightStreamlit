"""pages/realtime_monitor.py 頁面行為 AppTest。

見規格 docs/specs/pages/04-realtime-monitor.md §可測試性/TDD（測試 12–15）。
採 render-then-sample 執行序：首幀渲染依「進入該幀時的 rt_buffer」，故注入 rt_buffer
即可決定首幀畫面，無需 monkeypatch 生成器；閾值以注入 rt_threshold 控制。

註：st.fragment(run_every=1.0) 在 AppTest 下只執行首幀、不自動循環，故只測首幀行為。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib.models import Actor
from lib.realtime import Reading

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")

_TZ = timezone(timedelta(hours=8))
_NOW = datetime(2026, 7, 19, 12, 0, 3, tzinfo=_TZ)


def _open_monitor(actor: Actor, **state) -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = actor
    at.run()
    at.switch_page("pages/realtime_monitor.py")
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    return at


# 測試 12：初始化契約——未預設 rt_buffer / rt_tick 亦不 KeyError；viewer 亦可讀
def test_page_loads_without_state_for_any_grade():
    at = _open_monitor(Actor("viewer", "admin", grade="viewer"))
    assert not at.exception
    assert any("即時監控" in t.value for t in at.title)


# 測試 13：注入單筆緩衝（首幀即有資料）→ 含指標卡與閾值 slider
def test_buffer_with_data_shows_metrics_and_slider():
    at = _open_monitor(
        Actor("alice", "user"),
        rt_buffer=[Reading(ts=_NOW, value=42.0)],
    )
    assert not at.exception
    assert len(at.metric) >= 4
    sliders = [s for s in at.slider if s.label == "告警閾值"]
    assert sliders


# 測試 14：注入已知值 + 低閾值 → is_over 必為真 → 首幀以 st.toast 告警（不佔版面）
def test_over_threshold_renders_toast():
    at = _open_monitor(
        Actor("alice", "user"),
        rt_buffer=[Reading(ts=_NOW, value=50.0)],
        rt_threshold=10,
    )
    assert not at.exception
    assert at.toast
    assert any("告警" in t.value for t in at.toast)
    # 告警改用 toast overlay，不再佔版面（無 st.error），故圖表不因告警位移
    assert not at.error


# 測試 15：空 / 未預設 rt_buffer（首幀緩衝為空）→ 含 empty_state st.info，不渲染指標卡
def test_empty_buffer_shows_empty_state_and_no_metrics():
    at = _open_monitor(Actor("alice", "user"), rt_buffer=[])
    assert not at.exception
    assert any("串流啟動中" in i.value for i in at.info)
    assert len(at.metric) == 0
