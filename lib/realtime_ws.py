"""RealtimeWsClient — 背景 daemon 執行緒接 FastAPI WebSocket 推送即時讀值。

連線流程：
  1. POST {http_base}/ws/ticket  Bearer JWT → {"ticket": str, "expires_in": int}
  2. WS   {ws_base}/ws?ticket={ticket}
  3. 收 {"type":"welcome",...} → 送 {"type":"subscribe","topic":"realtime.stream"}
  4. 主迴圈：ping → pong；data → _on_reading；其他靜默

重連策略：
  - 4401 / 4409：停止重連，last_error 設值
  - 其他（網路 / 4000 / 1012 / 1013）：指數退避（1→2→4→...≤30s）

見規格 docs/specs/pages/04-realtime-ws-client.md。
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime
from typing import Callable

import httpx
import websockets
import websockets.exceptions

from lib.realtime import MAX_POINTS, Reading, trim

_logger = logging.getLogger(__name__)

_NON_RECONNECTABLE: frozenset[int] = frozenset({4401, 4409})


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


class RealtimeWsClient:
    """thread-safe WS client；Streamlit fragment 透過 .buffer / .last_error 讀快照。"""

    def __init__(
        self,
        *,
        http_base: str,
        ws_base: str,
        get_token: Callable[[], str],
    ) -> None:
        self._http_base = http_base
        self._ws_base = ws_base
        self._get_token = get_token
        self._lock = threading.Lock()
        self._buffer: list[Reading] = []
        self._last_error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """啟動 daemon 執行緒；若執行緒仍活著則 no-op（防重複呼叫）。"""
        if self._thread is not None and self._thread.is_alive():
            return
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

    def stop(self) -> None:
        """設定 stop 事件；執行緒於 backoff 等待結束後退出。"""
        self._stop.set()

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
