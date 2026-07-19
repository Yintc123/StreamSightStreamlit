"""RealtimeWsClient — 背景 daemon 執行緒接 FastAPI WebSocket 推送即時讀值。

連線流程：
  1. POST {http_base}/ws/ticket  Bearer JWT → {"ticket": str, "expires_in": int}
  2. WS   {ws_base}/ws?ticket={ticket}
  3. 收 {"type":"welcome",...} → 送 {"type":"subscribe","topic":"realtime.stream"}
  4. 主迴圈：ping → pong；data → _on_reading；其他靜默

重連策略：
  - 4401 / 4409：停止重連，last_error 設值
  - 其他（網路 / 4000 / 1012 / 1013）：指數退避（1→2→4→...≤30s）

生命週期（看門狗 / dead-man's switch）：
  - live_panel fragment 每秒 touch()；看門狗執行緒發現 >IDLE_STOP_SECONDS 未被 touch
    （切頁 / 關分頁 / 崩潰使 fragment 停止）→ 設 stop → 主動送 WS close → 執行緒退出。

見規格 docs/specs/pages/04-realtime-ws-client.md 與 04-realtime-ws-lifecycle.md。
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from typing import Callable

import httpx
import websockets
import websockets.exceptions

from lib.realtime import MAX_POINTS, Reading, trim

_logger = logging.getLogger(__name__)

_NON_RECONNECTABLE: frozenset[int] = frozenset({4401, 4409})

# 看門狗（dead-man's switch）：fragment 每秒 touch；超過 IDLE_STOP_SECONDS 未被 touch
# → 判定頁面已離開 / session 已結束 → 主動斷線。見規格 04-realtime-ws-lifecycle.md §1。
IDLE_STOP_SECONDS = 5.0    # run_every=1.0 下容忍約 4 次漏拍（rerun 抖動 / 整頁 rerun 空窗）
WATCHDOG_INTERVAL = 1.0    # 看門狗檢查週期


class _WsAuthError(Exception):
    """換票失敗（401）或無 token → _run_with_reconnect 停止重連。"""


async def _connect_and_subscribe(
    http_base: str,
    ws_base: str,
    get_token: Callable[[], str],
    on_reading: Callable[[Reading], None],
    stop: threading.Event,
) -> None:
    """一次完整連線：換票 → WS 握手 → 訂閱 → 接收迴圈。"""
    token = get_token()
    if not token:
        raise _WsAuthError("無 access token，無法換票（請先登入）")

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{http_base}/ws/ticket",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if resp.status_code == 401:
            raise _WsAuthError("access token 無效（401），無法換票")
        resp.raise_for_status()
        ticket = resp.json()["ticket"]

    uri = f"{ws_base}/ws?ticket={ticket}"
    async with websockets.connect(uri, open_timeout=10, close_timeout=5) as ws:
        welcome_raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        welcome = json.loads(welcome_raw)
        if welcome.get("type") != "welcome":
            raise ValueError(f"期望 welcome，收到 {welcome.get('type')!r}")

        await ws.send(json.dumps({"type": "subscribe", "topic": "realtime.stream"}))

        async for raw in ws:
            if stop.is_set():
                return
            msg = json.loads(raw)
            msg_type = msg.get("type")
            if msg_type == "ping":
                await ws.send(json.dumps({"type": "pong"}))
            elif msg_type == "data" and msg.get("topic") == "realtime.stream":
                ts = datetime.fromisoformat(msg["ts"]).astimezone()
                on_reading(Reading(ts=ts, value=float(msg["value"])))


def _run_with_reconnect(
    http_base: str,
    ws_base: str,
    get_token: Callable[[], str],
    on_reading: Callable[[Reading], None],
    on_error: Callable[[str], None],
    stop: threading.Event,
) -> None:
    """執行緒進入點：外層指數退避重連迴圈。loop 於 finally 關閉。"""
    loop = asyncio.new_event_loop()
    wait = 1.0
    try:
        while not stop.is_set():
            try:
                loop.run_until_complete(
                    _connect_and_subscribe(http_base, ws_base, get_token, on_reading, stop)
                )
                wait = 1.0
            except _WsAuthError as exc:
                on_error(str(exc))
                break
            except websockets.exceptions.ConnectionClosedError as exc:
                if exc.code in _NON_RECONNECTABLE:
                    on_error(f"WS 連線關閉（{exc.code}）")
                    break
                on_error(f"WS 連線中斷（{exc.code}），{int(wait)}s 後重連")
                stop.wait(timeout=wait)
                wait = min(wait * 2, 30.0)
            except Exception as exc:
                on_error(f"WS 連線失敗：{exc}，{int(wait)}s 後重連")
                stop.wait(timeout=wait)
                wait = min(wait * 2, 30.0)
    finally:
        loop.close()


def needs_new_client(existing: "RealtimeWsClient | None", use_mock: bool) -> bool:
    """api 模式下，client 不存在或已停止（看門狗斷線後）→ 需要建立新的。

    頁面守衛用：停留頁面的整頁 rerun → 既有 client is_alive → 重用；
    斷線後重回頁面 → 舊 client 已死 → 重建（新連線，buffer 從頭累積）。
    """
    return (not use_mock) and (existing is None or not existing.is_alive())


def _run_watchdog(
    seconds_since_touch: Callable[[], float],
    idle_stop: float,
    interval: float,
    stop: threading.Event,
) -> None:
    """看門狗執行緒：每 interval 秒檢查閒置；超過 idle_stop 未被 touch → 設 stop。

    stop.wait(timeout) 回傳 True（stop 已被設，含外部 stop()）即退出；False（逾時）則續查。
    設 stop 後：中斷連線執行緒的 backoff 等待、讓接收迴圈 return（送 WS close）、終止重連 while。
    """
    while not stop.wait(timeout=interval):
        if seconds_since_touch() > idle_stop:
            stop.set()
            return


class RealtimeWsClient:
    """thread-safe WS client；Streamlit fragment 透過 .buffer / .last_error 讀快照。"""

    def __init__(
        self,
        *,
        http_base: str,
        ws_base: str,
        get_token: Callable[[], str],
        idle_stop_seconds: float = IDLE_STOP_SECONDS,
    ) -> None:
        self._http_base = http_base
        self._ws_base = ws_base
        self._get_token = get_token
        self._idle_stop = idle_stop_seconds
        self._lock = threading.Lock()
        self._buffer: list[Reading] = []
        self._last_error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._watchdog: threading.Thread | None = None
        self._last_touch = time.monotonic()   # 心跳時戳；建構即給初值，避免 start 前誤判閒置

    def start(self) -> None:
        """啟動連線 daemon 執行緒 + 看門狗執行緒；若執行緒仍活著則 no-op（防重複呼叫）。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._last_touch = time.monotonic()   # 重置心跳，避免啟動瞬間即被判閒置
        self._thread = threading.Thread(
            target=_run_with_reconnect,
            args=(
                self._http_base,
                self._ws_base,
                self._get_token,
                self._on_reading,
                self._on_error,
                self._stop,
            ),
            daemon=True,
        )
        self._thread.start()
        # 看門狗檢查週期取 min(WATCHDOG_INTERVAL, idle_stop)：確保至少在 idle_stop 窗內檢查一次
        self._watchdog = threading.Thread(
            target=_run_watchdog,
            args=(
                self._seconds_since_touch,
                self._idle_stop,
                min(WATCHDOG_INTERVAL, self._idle_stop),
                self._stop,
            ),
            daemon=True,
        )
        self._watchdog.start()

    def stop(self) -> None:
        """設定 stop 事件；執行緒於 backoff 等待結束後退出。"""
        self._stop.set()

    def touch(self) -> None:
        """由 live_panel fragment 每次執行時呼叫；更新心跳時戳（thread-safe）。

        fragment 只在該頁被顯示時每秒執行，故「持續 touch」等價於「本頁仍在顯示」。
        """
        with self._lock:
            self._last_touch = time.monotonic()

    def _seconds_since_touch(self) -> float:
        """距上次 touch() 的秒數（thread-safe 快照）；看門狗據此判定閒置。"""
        with self._lock:
            return time.monotonic() - self._last_touch

    def is_alive(self) -> bool:
        """連線執行緒仍運行且未被要求停止 → True；供頁面判斷是否需重建 client。"""
        return (
            self._thread is not None
            and self._thread.is_alive()
            and not self._stop.is_set()
        )

    @property
    def buffer(self) -> list[Reading]:
        """thread-safe 快照（copy）。"""
        with self._lock:
            return list(self._buffer)

    @property
    def last_error(self) -> str | None:
        """最近一次失敗訊息；None = 正常或已恢復。"""
        with self._lock:
            return self._last_error

    def _on_reading(self, reading: Reading) -> None:
        with self._lock:
            self._buffer = trim(self._buffer + [reading], MAX_POINTS)
            self._last_error = None

    def _on_error(self, message: str) -> None:
        _logger.warning("realtime_ws: %s", message)
        with self._lock:
            self._last_error = message
