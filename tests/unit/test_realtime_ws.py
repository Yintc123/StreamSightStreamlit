"""lib/realtime_ws 單元測試（測試 19–22）。

見規格 docs/specs/pages/04-realtime-ws-client.md §10.1。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from lib.realtime import MAX_POINTS, Reading
from lib.realtime_ws import RealtimeWsClient


def _client() -> RealtimeWsClient:
    return RealtimeWsClient(
        http_base="http://x",
        ws_base="ws://x",
        get_token=lambda: "test-token",
    )


def _reading(value: float = 50.0) -> Reading:
    return Reading(ts=datetime.now(timezone.utc).astimezone(), value=value)


# --- 19. _on_reading 更新緩衝 + trim ---

def test_on_reading_appends_to_buffer():
    c = _client()
    r = _reading()
    c._on_reading(r)
    assert c.buffer == [r]


def test_on_reading_multiple_readings_ordered():
    c = _client()
    r1, r2 = _reading(10.0), _reading(20.0)
    c._on_reading(r1)
    c._on_reading(r2)
    assert c.buffer == [r1, r2]


def test_on_reading_trims_to_max_points():
    c = _client()
    for i in range(MAX_POINTS + 10):
        c._on_reading(_reading(float(i % 100)))
    assert len(c.buffer) == MAX_POINTS


def test_buffer_returns_copy():
    """buffer property 回傳 copy；呼叫端修改不影響內部狀態。"""
    c = _client()
    c._on_reading(_reading())
    snap = c.buffer
    snap.clear()
    assert len(c.buffer) == 1


# --- 20. _on_error 設 last_error；收到資料後自動清除 ---

def test_on_error_sets_last_error():
    c = _client()
    c._on_error("bad connection")
    assert c.last_error == "bad connection"


def test_on_error_overwrites_previous():
    c = _client()
    c._on_error("first error")
    c._on_error("second error")
    assert c.last_error == "second error"


def test_last_error_initial_is_none():
    assert _client().last_error is None


def test_on_reading_clears_last_error():
    c = _client()
    c._on_error("bad")
    c._on_reading(_reading())
    assert c.last_error is None


# --- 21. stop() 中斷 backoff，執行緒能正常退出 ---

def test_stop_interrupts_backoff(monkeypatch):
    """stop() 後執行緒應於 < 2s 退出（不因 backoff wait 掛住）。"""
    import lib.realtime_ws as _ws_module

    async def _always_fail(*_args, **_kwargs):
        raise Exception("強制失敗，觸發 backoff")

    monkeypatch.setattr(_ws_module, "_connect_and_subscribe", _always_fail)

    c = _client()
    c.start()
    time.sleep(0.2)   # 讓執行緒至少跑一次 backoff
    c.stop()

    assert c._thread is not None
    c._thread.join(timeout=2.0)
    assert not c._thread.is_alive(), "執行緒應已退出，但仍在執行"


def test_start_idempotent(monkeypatch):
    """start() 重複呼叫不重建執行緒。"""
    import lib.realtime_ws as _ws_module

    async def _block_forever(*_args, **_kwargs):
        import asyncio
        await asyncio.sleep(60)

    monkeypatch.setattr(_ws_module, "_connect_and_subscribe", _block_forever)

    c = _client()
    c.start()
    first_thread = c._thread
    c.start()   # 第二次呼叫
    assert c._thread is first_thread
    c.stop()
    c._thread.join(timeout=2.0)


# --- 22. UTC ts → 本地時區轉換 ---

def test_utc_ts_converts_to_local_aware():
    """_connect_and_subscribe 的 UTC ISO 字串，經 astimezone() 轉為本地 aware datetime。"""
    utc_ts = "2026-07-19T12:00:01.000000+00:00"
    ts = datetime.fromisoformat(utc_ts).astimezone()
    r = Reading(ts=ts, value=42.3)

    c = _client()
    c._on_reading(r)

    stored = c.buffer[-1]
    assert stored.ts.tzinfo is not None
    assert stored.ts.utcoffset() is not None
    assert stored.value == 42.3


def test_reading_value_float_precision():
    """value 浮點數精度保留，不四捨五入。"""
    c = _client()
    c._on_reading(Reading(ts=datetime.now(timezone.utc).astimezone(), value=42.3))
    assert c.buffer[-1].value == 42.3


# --- 回歸：get_token 在執行緒啟動時才呼叫（捕獲主執行緒讀取的值） ---

def test_get_token_called_at_connect_not_at_construction():
    """get_token 由背景執行緒在換票前呼叫；若 callable 捕獲的值為空字串，
    _on_error 應被呼叫，last_error 應設為認證失敗訊息。

    此測試模擬「主執行緒讀 token 後以 lambda 傳入」的正確用法：
    get_token=lambda: captured_token（captured_token 在主執行緒已讀取）。
    """
    import lib.realtime_ws as _ws_module

    calls = []

    async def _fake_connect(http_base, ws_base, get_token, on_reading, stop):
        token = get_token()
        calls.append(token)
        if not token:
            raise _ws_module._WsAuthError("無 access token，無法換票（請先登入）")

    monkeypatch_obj = None   # 此 test 不用 monkeypatch，直接 setattr

    original = _ws_module._connect_and_subscribe
    _ws_module._connect_and_subscribe = _fake_connect
    try:
        captured_token = ""   # 模擬主執行緒讀到空 token（未登入）
        c = RealtimeWsClient(
            http_base="http://x",
            ws_base="ws://x",
            get_token=lambda: captured_token,
        )
        c.start()
        c._thread.join(timeout=2.0)
        assert not c._thread.is_alive()
        assert c.last_error is not None
        assert "access token" in c.last_error
        assert calls == [""]   # 確認 get_token() 在執行緒內被呼叫且拿到空值
    finally:
        _ws_module._connect_and_subscribe = original
