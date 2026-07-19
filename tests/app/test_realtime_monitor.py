"""pages/realtime_monitor.py 頁面行為 AppTest。

見規格 docs/specs/pages/04-realtime-monitor.md §可測試性/TDD（測試 14–17）
與 docs/specs/pages/04-realtime-ws-client.md §10.2（測試 23–25）。

採 render-then-sample 執行序：首幀渲染依「進入該幀時的 rt_buffer」，故注入 rt_buffer
即可決定首幀畫面，無需 monkeypatch 生成器；閾值以注入 rt_threshold 控制。

AppTest 從 app.py 進入再 switch_page；use_mock=False 時需 patch resolve_actor 繞過 BFF。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib.models import Actor, AdminRole
from lib.realtime import Reading

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")
RT_PATH = str(Path(__file__).resolve().parents[2] / "pages" / "realtime_monitor.py")

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


# 測試 14：初始化契約——未預設 rt_buffer / rt_tick 亦不 KeyError；viewer 亦可讀
def test_page_loads_without_state_for_any_grade():
    at = _open_monitor(Actor("viewer", "admin", grade=AdminRole.VIEWER))
    assert not at.exception
    assert any("即時監控" in t.value for t in at.title)


# 測試 15：注入單筆緩衝（首幀即有資料）→ 含指標卡與閾值 slider
def test_buffer_with_data_shows_metrics_and_slider():
    at = _open_monitor(
        Actor("alice", "user"),
        rt_buffer=[Reading(ts=_NOW, value=42.0)],
    )
    assert not at.exception
    assert len(at.metric) >= 4
    sliders = [s for s in at.slider if s.label == "告警閾值"]
    assert sliders


# 測試 16：注入已知值 + 低閾值 → is_over 必為真 → 首幀以 st.toast 告警（不佔版面）
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


# 測試 17：空 / 未預設 rt_buffer（首幀緩衝為空）→ 含 empty_state st.info，不渲染指標卡
def test_empty_buffer_shows_empty_state_and_no_metrics():
    at = _open_monitor(Actor("alice", "user"), rt_buffer=[])
    assert not at.exception
    assert any("串流啟動中" in i.value for i in at.info)
    assert len(at.metric) == 0


# ── 測試 23–25：use_mock=False（WS client 路徑）────────────────────────────────
#
# use_mock=False 時，resolve_actor() 走 BFF（session_state["actor"] 被忽略）。
# _open_monitor_api：patch lib.auth.resolve_actor 繞過 BFF；page 的 require_auth()
# 讀 state.get_actor()（session_state["actor"]），由 _open_monitor_api 注入即可通過。


class _MockWsClient:
    """注入用的假 WsClient；不啟動執行緒，不連真實後端。"""

    def __init__(self, buffer=None, last_error=None, alive=True):
        self._buf = buffer or []
        self._last_error = last_error
        self.started = False
        self.stopped = False
        self.touch_count = 0
        self._alive = alive

    def start(self): self.started = True
    def stop(self): self.stopped = True
    def touch(self): self.touch_count += 1
    def is_alive(self): return self._alive

    @property
    def buffer(self): return list(self._buf)

    @property
    def last_error(self): return self._last_error


def _open_monitor_api(actor: Actor, monkeypatch, **state) -> AppTest:
    """use_mock=False AppTest helper：直接測頁面，繞過 app.py auth dance。

    require_auth() 在 use_mock=False + session_state["actor"] 已設時自動通過。
    不需穿越 app.py 的 BFF resolve_actor 邏輯。
    """
    monkeypatch.setenv("USE_MOCK", "false")
    at = AppTest.from_file(RT_PATH)
    at.session_state["actor"] = actor
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    return at


# 測試 23：WS buffer 有資料 → 顯示指標卡，不顯示 empty_state
def test_ws_buffer_with_data_shows_metrics(monkeypatch):
    at = _open_monitor_api(
        Actor("alice", "admin", grade=AdminRole.VIEWER),
        monkeypatch,
        rt_ws_client=_MockWsClient(buffer=[Reading(ts=_NOW, value=42.0)]),
    )
    assert not at.exception
    assert len(at.metric) >= 4
    assert not any("串流啟動中" in i.value for i in at.info)


# 測試 24：WS last_error 有值 → 顯示 st.error，不渲染指標卡
def test_ws_last_error_shows_error_no_metrics(monkeypatch):
    at = _open_monitor_api(
        Actor("alice", "admin", grade=AdminRole.VIEWER),
        monkeypatch,
        rt_ws_client=_MockWsClient(last_error="connection refused"),
    )
    assert not at.exception
    assert at.error
    assert len(at.metric) == 0


# 測試 25：WS buffer 為空、last_error 為 None → 顯示 empty_state，不渲染指標卡
def test_ws_empty_buffer_shows_empty_state(monkeypatch):
    at = _open_monitor_api(
        Actor("alice", "admin", grade=AdminRole.VIEWER),
        monkeypatch,
        rt_ws_client=_MockWsClient(buffer=[], last_error=None),
    )
    assert not at.exception
    assert any("串流啟動中" in i.value for i in at.info)
    assert len(at.metric) == 0


# ── 測試 32–33：連線生命週期（心跳 / 死連線重建）─────────────────────────────
# 見 docs/specs/pages/04-realtime-ws-lifecycle.md §7.2。


# 測試 32：live_panel 每次 render 呼叫 touch()（心跳存在 → 看門狗不誤斷）
def test_live_panel_touches_client(monkeypatch):
    mock = _MockWsClient(buffer=[Reading(ts=_NOW, value=42.0)], alive=True)
    at = _open_monitor_api(
        Actor("alice", "admin", grade=AdminRole.VIEWER),
        monkeypatch,
        rt_ws_client=mock,
    )
    assert not at.exception
    assert mock.touch_count >= 1


# 測試 33：注入「已死」client → 頁面重建新 client（不重用舊的）
def test_dead_client_is_replaced(monkeypatch):
    created = {}

    class _Spy(_MockWsClient):
        def __init__(self, **_kwargs):        # 吞掉 http_base/ws_base/get_token
            super().__init__(alive=True)
            created["new"] = self

    # 頁面 `from lib.realtime_ws import RealtimeWsClient` 於 at.run() re-exec 時取到 spy
    monkeypatch.setattr("lib.realtime_ws.RealtimeWsClient", _Spy)

    dead = _MockWsClient(alive=False)
    at = _open_monitor_api(
        Actor("alice", "admin", grade=AdminRole.VIEWER),
        monkeypatch,
        rt_ws_client=dead,
    )
    assert not at.exception
    assert "new" in created                   # 已死 → 重建
    assert created["new"].started is True      # 新 client 有 start()
    assert dead.touch_count == 0               # 舊的未被使用
