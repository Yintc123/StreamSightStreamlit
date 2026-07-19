# 規格書：即時監控 WebSocket Client（前端接後端 WS Cycle）

> 狀態：**待實作** ／ 開發模式：**嚴格 TDD（見 `CLAUDE.md`）**
>
> **語言**：繁體中文。
>
> 前置條件：後端 WebSocket 模組（`websocket.md`）與即時串流生成器（`realtime-stream.md`）均已實作完成並通過測試。**本規格定義 Streamlit 前端側**，從 mock 切換至 FastAPI WebSocket 的完整實作與 TDD 計畫。
>
> 🔗 延伸既有規格：[04-realtime-monitor.md](./04-realtime-monitor.md)（版面、純函式、mock 模式、session_state 契約、測試 1–17）。本規格新增測試 18–25，並以**後端實際 API** 為單一真相定義所有介面細節。

---

## 0. 功能總覽

**三個檔案改動，合計約 130 行：**

| 檔案 | 動作 |
|---|---|
| `lib/config.py` | 新增 `fastapi_ws_url` property（`http→ws` 協定替換） |
| `lib/realtime_ws.py` | **新建**；`RealtimeWsClient`（daemon 執行緒 + asyncio loop） |
| `pages/realtime_monitor.py` | 補 3 個 import；`live_panel()` 改讀 `ws.buffer` |

**頁面版面與純函式（`lib/realtime.py`）完全不變**——只替換「取值來源」。

---

## 1. 後端 API 契約（實作依據，單一真相）

> 以下均已在後端實作完成，前端只需對接。

### 1.1 兩段式認證流程

```
① HTTP  POST /ws/ticket
        Authorization: Bearer {access_token}
     ← 200 {"ticket": "<opaque>", "expires_in": 180}

② WS    ws://{host}/ws?ticket={ticket}
     → server accept
     ← {"type": "welcome", "connection_id": "<uuid>", "admin_role": 0}
     → {"type": "subscribe", "topic": "realtime.stream"}
     ← {"type": "subscribed", "topic": "realtime.stream"}
     ← {"type": "data", "topic": "realtime.stream", "value": 42.3, "ts": "2026-07-19T12:00:01.000000+00:00"}
        …每秒一筆…
```

- ticket 為**短命（TTL 180s）、單次（GETDEL）**；換票後應立即建立 WS 連線。
- WS URL 不帶 Authorization header；長命 token **不進 URL**（安全設計）。
- `access_token` 由 `lib/state.get_token()` 讀取（存於 `st.session_state["access_token"]`）。

### 1.2 WS 訊息協定（前端需處理的全套）

**server → client**

| `type` | 欄位 | 前端行為 |
|---|---|---|
| `welcome` | `connection_id`, `admin_role` | 確認後送 subscribe |
| `subscribed` | `topic` | 確認訂閱，進入主迴圈 |
| `ping` | — | **必須回** `{"type":"pong"}`；否則後端連續 2 次未回 → `close(4000)` |
| `data` | `topic`, `value`, `ts` | `topic=="realtime.stream"` 時呼叫 `_on_reading`；其他靜默跳過 |
| `error` | `code`, `message` | 非致命，記錄 log，連線續存 |
| `unsubscribed` | `topic` | 非預期，靜默忽略 |

**client → server**

| `type` | 時機 |
|---|---|
| `subscribe` + `topic: "realtime.stream"` | welcome 後立即送 |
| `pong` | 每次收到 ping 後立即回 |

> **重要**：`realtime.stream` 資料使用 `type="data"` 而非通用的 `type="event"`（後端 `realtime-stream.md §4.1`）。

### 1.3 連線關閉碼與前端策略

| Code | 含義 | 前端策略 |
|---|---|---|
| `4401` | 認證失效 / kick | **停止重連**；`last_error` 設值 |
| `4409` | 同 (sid, cid) 被取代 | **停止重連**（靜默；Streamlit 單 session 不應出現） |
| `4000` | Heartbeat timeout | 指數退避重連 |
| `4400` | 協定錯誤 | 指數退避重連 + log |
| `1012` | 服務重啟 | 指數退避重連 |
| `1013` | 背壓 | 指數退避重連 |
| 網路錯誤 | 逾時 / 斷線 | 指數退避重連 |

### 1.4 資料訊息欄位

```json
{"type": "data", "topic": "realtime.stream", "value": 42.3, "ts": "2026-07-19T12:00:01.000000+00:00"}
```

| 欄位 | 型別 | 說明 |
|---|---|---|
| `value` | `float` | `[0.0, 100.0]`，一位小數 |
| `ts` | ISO 8601 UTC（`+00:00`） | 消費層轉本地時區：`datetime.fromisoformat(ts).astimezone()` |

---

## 2. lib/config.py：fastapi_ws_url property

在 `BaseAppSettings` 加入：

```python
@property
def fastapi_ws_url(self) -> str:
    """http(s) → ws(s)；先換 https，再換 http，避免 https 雙重替換。"""
    return (
        self.fastapi_base_url
        .replace("https://", "wss://")
        .replace("http://", "ws://")
    )
```

**替換順序釘死**：`https://` 含 `http` 前綴，必須先處理；否則 `https://` 先被換成 `wss//`（雙斜線缺失），後續 `http→ws` 找不到 `http://` 也不報錯。

---

## 3. lib/realtime_ws.py（新建）

### 3.1 設計約束

| 約束 | 原因 |
|---|---|
| **daemon 執行緒 + 獨立 `asyncio.new_event_loop()`** | Streamlit session 單執行緒；WS 長連線不能阻塞主執行緒 |
| **`threading.Lock` 保護 `_buffer` / `_last_error`** | 背景執行緒寫、主執行緒讀；不直接寫 `st.session_state`（跨執行緒不安全） |
| **`get_token: Callable[[], str]`** | 每次重連呼叫，確保拿最新 token；測試可注入 stub |
| **`stop.wait(timeout=wait)` 退避** | `stop.set()` 後立即中斷等待，不讓 session 結束後仍掛起 |
| **`self._thread` 儲存執行緒參照** | 防止重複 `start()`；測試 21 可 `join()` 驗退出 |
| **`loop.close()` 於 finally** | 事件迴圈資源不洩漏 |

### 3.2 完整模組結構（含 import block 與所有實作細節）

```python
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

# 收到這些 close code 不重連（認證失效 / 同分頁取代）
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
    """一次完整連線：換票 → WS 握手 → 訂閱 → 接收迴圈。

    正常結束（stop.is_set()）→ return；
    異常由 _run_with_reconnect 捕獲並決定是否重連。
    """
    # ── 1. 換票（HTTP，每次重連都取最新 token）──────────────────────────────
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

    # ── 2. WS 連線、握手、訂閱、接收 ─────────────────────────────────────
    uri = f"{ws_base}/ws?ticket={ticket}"
    async with websockets.connect(uri, open_timeout=10, close_timeout=5) as ws:
        # (a) welcome（第一則訊息）
        welcome_raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        welcome = json.loads(welcome_raw)
        if welcome.get("type") != "welcome":
            raise ValueError(f"期望 welcome，收到 {welcome.get('type')!r}")

        # (b) 送訂閱請求
        await ws.send(json.dumps({"type": "subscribe", "topic": "realtime.stream"}))

        # (c) 主迴圈：subscribed / ping / data 統一在此處理
        async for raw in ws:
            if stop.is_set():
                return
            msg = json.loads(raw)
            msg_type = msg.get("type")
            if msg_type == "ping":
                await ws.send(json.dumps({"type": "pong"}))
            elif msg_type == "data" and msg.get("topic") == "realtime.stream":
                ts = datetime.fromisoformat(msg["ts"]).astimezone()  # UTC → 本地時區
                on_reading(Reading(ts=ts, value=float(msg["value"])))
            # subscribed / error / unsubscribed → 靜默（非致命，不影響資料流）


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
                wait = 1.0   # 正常結束 → stop 已設定，while 條件 False，退出
            except _WsAuthError as exc:
                on_error(str(exc))
                break        # 認證失敗：不重連
            except websockets.exceptions.ConnectionClosedError as exc:
                if exc.code in _NON_RECONNECTABLE:
                    on_error(f"WS 連線關閉（{exc.code}）")
                    break    # 不重連
                on_error(f"WS 連線中斷（{exc.code}），{int(wait)}s 後重連")
                stop.wait(timeout=wait)
                wait = min(wait * 2, 30.0)
            except Exception as exc:
                on_error(f"WS 連線失敗：{exc}，{int(wait)}s 後重連")
                stop.wait(timeout=wait)
                wait = min(wait * 2, 30.0)
    finally:
        loop.close()   # 資源清理；不論正常退出或例外皆執行


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
        self._thread: threading.Thread | None = None  # 儲存 ref 供 stop() 與測試

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
            daemon=True,   # session 結束後隨 process 退出，不阻止 Python 終止
        )
        self._thread.start()

    def stop(self) -> None:
        """設定 stop 事件；執行緒於 backoff 等待結束後退出（最多 30s）。"""
        self._stop.set()

    @property
    def buffer(self) -> list[Reading]:
        """thread-safe 快照（copy）；不持有 lock 給呼叫端。"""
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
            self._last_error = None   # 成功收到資料 → 清除錯誤（連線恢復）

    def _on_error(self, message: str) -> None:
        _logger.warning("realtime_ws: %s", message)
        with self._lock:
            self._last_error = message
        # 不清緩衝：斷線期間 .buffer 保留最後已知值，恢復後 fragment 自動切回圖表
```

---

## 4. pages/realtime_monitor.py：改動

### 4.0 需新增的 import（現有頁面缺少，必須補）

```python
# 在現有 import 區塊末尾加入這三行
from lib.config import get_settings
from lib.realtime_ws import RealtimeWsClient
from lib import state as _state
```

並在 `require_auth()` 之後立即加入：

```python
settings = get_settings()
```

> **`settings` 為頁面層級變數**，fragment 內外皆可讀取。`get_settings()` 有 `lru_cache`，多次呼叫不重建物件。
> **不需要 `from lib.errors import render_error`**——WS 錯誤直接以 `st.error(ws.last_error)` 呈現（見 §4.2 說明）。

### 4.1 fragment 外：初始化 WsClient（一次性）

在 `st.session_state.setdefault("rt_tick", 0)` 之後、`st.slider` 之前加入：

```python
if not settings.use_mock and "rt_ws_client" not in st.session_state:
    _ws = RealtimeWsClient(
        http_base=settings.fastapi_base_url,
        ws_base=settings.fastapi_ws_url,
        get_token=lambda: _state.get_token() or "",
    )
    _ws.start()
    st.session_state["rt_ws_client"] = _ws
```

**`_state.get_token() or ""`** 而非 `st.session_state.get("access_token", "")`——使用模組存取層，隔離 key 字串耦合；lambda 在每次重連時才呼叫，確保拿最新 token。

### 4.2 live_panel()：buffer 來源切換

```python
@st.fragment(run_every=1.0)
def live_panel() -> None:
    # ── 1) 取 buffer（mock / api 二選一）──────────────────────────────────
    if not settings.use_mock:
        _ws: RealtimeWsClient = st.session_state["rt_ws_client"]
        if _ws.last_error:
            st.error(_ws.last_error)   # WS 連線錯誤直接顯示原始訊息
            return                     # early return → run_every 繼續，連線恢復後自動回圖表
        buffer = _ws.buffer
    else:
        buffer = st.session_state["rt_buffer"]

    # ── 2) 渲染（不變）──────────────────────────────────────────────────
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

    # ── 3) 模擬生成（mock 專屬）──────────────────────────────────────────
    if settings.use_mock:
        tick = st.session_state["rt_tick"]
        reading = Reading(ts=datetime.now().astimezone(), value=sample_value(tick))
        st.session_state["rt_buffer"] = trim(buffer + [reading], MAX_POINTS)
        st.session_state["rt_tick"] = tick + 1
```

### 4.3 為何用 `st.error(ws.last_error)` 而非 `render_error`

`render_error(exc: Exception)` 的簽名接受的是 **Exception 物件**，並透過 `to_user_message` 把 `ApiError`/`PermissionDenied` 等結構化例外翻成對使用者友善的固定文案（例如 `ApiError(status=None)` → "暫時無法連線,請稍後重試"，刻意隱藏技術細節）。

WS client 的 `last_error` 是 `str`，儲存的是 WS 層的原始操作訊息（連線中斷原因、backoff 狀態），**不是** REST API 契約錯誤——強行包裝成 `ApiError` 再傳給 `render_error` 會丟失具體資訊（顯示固定文案而非實際原因），對管理員除錯毫無幫助。

因此 WS 錯誤直接用 `st.error(ws.last_error)` 呈現原始訊息，`render_error` 仍供 REST API 呼叫失敗使用，兩者職責不重疊。

---

## 5. 錯誤處理

| 情境 | 呈現 | 備註 |
|---|---|---|
| 緩衝為空（WS 尚未收到第一筆） | `empty_state("資料串流啟動中…")` | 同 mock 首幀 |
| 目前值 > 閾值 | toast overlay + 「目前值」卡 inverse delta | 同 mock |
| ticket 取得失敗（401） | `st.error(ws.last_error)` + `return`，**停止重連** | `_WsAuthError` → `on_error` → `last_error` |
| ticket 取得失敗（5xx） | `st.error(ws.last_error)` 暫顯，背景退避重連 | `raise_for_status` → `Exception` |
| WS 認證失敗（`close 4401`） | `st.error(ws.last_error)` + `return`，**停止重連** | 帳號封存 / kick |
| WS 連線中斷（4000/1012/1013/網路） | `st.error(ws.last_error)` 暫顯，背景退避重連；恢復後 `last_error` 清除，自動切回圖表 | `.buffer` 保留最後已知值 |

---

## 6. session_state 契約（新增 key）

**新增（`use_mock=False` 時）：**

| Key | 型別 | 說明 | 生命週期 |
|---|---|---|---|
| `rt_ws_client` | `RealtimeWsClient` | WS client；daemon 執行緒持有 `_buffer`/`_lock`；fragment 透過 `.buffer`/`.last_error` 讀快照 | 頁面初始化時建立；session 結束時 daemon 隨 process 退出 |

現有 `rt_buffer`/`rt_tick`（api 模式仍 `setdefault` 初始化，但只在 mock 模式讀寫）、`rt_threshold` 不變。

---

## 7. mock vs api 模式行為

| 面向 | `use_mock=True` | `use_mock=False` |
|---|---|---|
| 取值來源 | `sample_value(tick)` | `RealtimeWsClient.buffer` |
| token 需求 | 無 | 需要有效 `access_token` |
| 初始空值 | 首幀天然為空 | 背景執行緒連線中，直到第一筆 push 到達 |
| 錯誤呈現 | 無 | `st.error(ws.last_error)` 暫顯，連線恢復後自動清除 |
| `rt_ws_client` | 不建立 | 頁面進入時建立並 start |

---

## 8. 依賴

| 套件 | 用途 | 狀態 |
|---|---|---|
| `websockets` | async WS 連線（`websockets.connect`）| **需 `uv add websockets`** |
| `httpx` | 換票 HTTP 呼叫（`httpx.AsyncClient`）| 已存在 |

> `httpx.AsyncClient`（而非 `httpx.Client`）：於 `asyncio.new_event_loop()` context 內必須用非同步版本，避免跨 loop 問題。

---

## 9. 可測試性設計原則

| 設計 | 測試效益 |
|---|---|
| `get_token: Callable` | 注入 `lambda: "test-token"`，不依賴 `st.session_state` |
| `_on_reading` / `_on_error` 為 public-ish 方法（單底線） | 直接呼叫驗緩衝，不需啟動執行緒 |
| `self._thread` 儲存 | 測試 21 可 `client._thread.join(timeout=2)` 驗退出 |
| `_connect_and_subscribe` 為模組層級 async 函式 | 可 monkeypatch `lib.realtime_ws._connect_and_subscribe` |
| AppTest 注入 mock client 至 `session_state["rt_ws_client"]` | 不啟動真實執行緒；`monkeypatch.setenv("USE_MOCK", "false")` 觸發 api 路徑 |

---

## 10. TDD 測試計畫（18–25）

> 延伸 `04-realtime-monitor.md` 測試 1–17；編號接續。
>
> **測試環境基礎**：`tests/conftest.py` 的 `autouse` fixture 在每個測試前自動執行 `get_settings.cache_clear()` 並設 `APP_ENV=test`（`TestSettings`，`use_mock=True`）。測試只需額外 `monkeypatch.setenv(...)` 即可覆寫特定欄位。

### 10.1 Unit — `tests/unit/test_config.py` 與 `tests/unit/test_realtime_ws.py`

#### 18. `fastapi_ws_url` property 協定替換

```python
# tests/unit/test_config.py（加在現有測試末尾）
def test_fastapi_ws_url_http(monkeypatch):
    monkeypatch.setenv("FASTAPI_BASE_URL", "http://localhost:3001")
    assert get_settings().fastapi_ws_url == "ws://localhost:3001"

def test_fastapi_ws_url_https(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("FASTAPI_BASE_URL", "https://api.example.com")
    assert get_settings().fastapi_ws_url == "wss://api.example.com"

def test_fastapi_ws_url_no_double_replace(monkeypatch):
    """https 不可被替換成 wsss（雙重替換 bug）。"""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("FASTAPI_BASE_URL", "https://api.example.com")
    result = get_settings().fastapi_ws_url
    assert result.startswith("wss://")
    assert "wsss" not in result
```

> `autouse` fixture 已清快取並設 `APP_ENV=test`；各測試視需要覆寫 env 即可，不需手動清快取。

#### 19. `_on_reading` 更新緩衝 + trim

```python
# tests/unit/test_realtime_ws.py
from datetime import datetime, timezone
from lib.realtime import MAX_POINTS, Reading
from lib.realtime_ws import RealtimeWsClient

def _client():
    return RealtimeWsClient(http_base="http://x", ws_base="ws://x", get_token=lambda: "t")

def test_on_reading_appends_to_buffer():
    c = _client()
    r = Reading(ts=datetime.now(timezone.utc).astimezone(), value=50.0)
    c._on_reading(r)
    assert c.buffer == [r]

def test_on_reading_trims_to_max_points():
    c = _client()
    for i in range(MAX_POINTS + 10):
        c._on_reading(Reading(ts=datetime.now(timezone.utc).astimezone(), value=float(i % 100)))
    assert len(c.buffer) == MAX_POINTS
```

#### 20. `_on_error` 設 `last_error`；收到資料後自動清除

```python
def test_on_error_sets_last_error():
    c = _client()
    c._on_error("bad connection")
    assert c.last_error == "bad connection"

def test_on_reading_clears_last_error():
    c = _client()
    c._on_error("bad")
    c._on_reading(Reading(ts=datetime.now(timezone.utc).astimezone(), value=10.0))
    assert c.last_error is None
```

#### 21. `stop()` 中斷 backoff，執行緒能正常退出

```python
import lib.realtime_ws as _ws_module

def test_stop_interrupts_backoff(monkeypatch):
    """stop() 後執行緒應於 < 2s 退出（不因 backoff wait=30s 掛住）。"""
    async def _always_fail(*_args, **_kwargs):
        raise Exception("強制失敗，觸發 backoff")

    monkeypatch.setattr(_ws_module, "_connect_and_subscribe", _always_fail)

    c = _client()
    c.start()
    # 讓執行緒至少跑一次 backoff
    import time; time.sleep(0.2)
    c.stop()

    assert c._thread is not None
    c._thread.join(timeout=2.0)
    assert not c._thread.is_alive(), "執行緒應已退出，但仍在執行"
```

#### 22. UTC ts → 本地時區轉換

```python
def test_on_reading_converts_utc_to_local():
    """_connect_and_subscribe 的 UTC ts 字串，經 astimezone() 轉為 local-aware datetime。"""
    # 直接模擬 _connect_and_subscribe 消費一條 data 訊息的邏輯
    utc_ts = "2026-07-19T12:00:01.000000+00:00"
    ts = datetime.fromisoformat(utc_ts).astimezone()
    r = Reading(ts=ts, value=42.3)

    c = _client()
    c._on_reading(r)

    stored = c.buffer[-1]
    assert stored.ts.tzinfo is not None          # aware（有時區資訊）
    assert stored.ts.utcoffset() is not None     # 非 naive
    # 驗 value 正確轉型
    assert stored.value == 42.3
```

### 10.2 頁面行為（`tests/app/test_realtime_monitor.py`，AppTest）

> 以 mock `RealtimeWsClient` 注入 `session_state["rt_ws_client"]`。
> `monkeypatch.setenv("USE_MOCK", "false")` 觸發 api 路徑（`autouse` 已清快取，此 setenv 後 `get_settings()` 回 `TestSettings(use_mock=False)`）。
> AppTest 從 `app.py` 進入再 `switch_page`，延續既有 14–17 的 `_open_monitor` helper。

**共用 helper（放在測試模組頂層）**：

```python
class _MockWsClient:
    """注入用的假 WsClient；不啟動執行緒，不連真實後端。"""
    def __init__(self, buffer=None, last_error=None):
        self._buf = buffer or []
        self.last_error = last_error
        self.started = False

    def start(self): self.started = True
    def stop(self): pass

    @property
    def buffer(self): return list(self._buf)
```

#### 23. WS buffer 有資料 → 顯示指標卡，不顯示 empty_state

```python
def test_ws_buffer_with_data_shows_metrics(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "false")
    at = _open_monitor(
        Actor("alice", "admin", grade=AdminRole.VIEWER),
        rt_ws_client=_MockWsClient(buffer=[Reading(ts=_NOW, value=42.0)]),
    )
    assert not at.exception
    assert len(at.metric) >= 4
    assert not any("串流啟動中" in i.value for i in at.info)
```

#### 24. WS `last_error` 有值 → 顯示 `st.error`，不渲染指標卡

```python
def test_ws_last_error_shows_error_no_metrics(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "false")
    at = _open_monitor(
        Actor("alice", "admin", grade=AdminRole.VIEWER),
        rt_ws_client=_MockWsClient(last_error="connection refused"),
    )
    assert not at.exception
    assert at.error                  # st.error 有輸出
    assert len(at.metric) == 0       # early return → 不渲染指標卡
```

#### 25. WS buffer 為空、`last_error` 為 None → 顯示 empty_state，不渲染指標卡

```python
def test_ws_empty_buffer_shows_empty_state(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "false")
    at = _open_monitor(
        Actor("alice", "admin", grade=AdminRole.VIEWER),
        rt_ws_client=_MockWsClient(buffer=[], last_error=None),
    )
    assert not at.exception
    assert any("串流啟動中" in i.value for i in at.info)
    assert len(at.metric) == 0
```

---

## 11. 實作順序（TDD 里程碑）

依 `CLAUDE.md` Red→Green→Refactor，先寫失敗測試再補實作：

1. **`lib/config.py` property**（測試 18 × 3 先紅 → 補 property → 全綠）
2. **`uv add websockets`**（測試 19 起需要）
3. **`lib/realtime_ws.py`**（依序 19 → 20 → 21 → 22；一測試一小步）
4. **`pages/realtime_monitor.py`**（AppTest 23 → 24 → 25；加 import + settings + WsClient 初始化 + live_panel 分支）
5. **全套 `pytest` 通過**，含既有 1–17

---

## 12. 已定案決策

- ✅ **`get_token` Callable 接縫**：每次重連呼叫，確保拿最新 token；lambda 不耦合 Streamlit 狀態，測試可注入 stub。
- ✅ **`threading.Lock` 保護 `_buffer`/`_last_error`**：不直接寫 `st.session_state`，避免跨執行緒 Streamlit 內部衝突。
- ✅ **`last_error: str | None`，不用 Exception**：WS 連線錯誤是操作層訊息，不適合 `render_error`（接 Exception、顯示固定文案）；`st.error(str)` 直接顯示原始原因，對管理員除錯更有幫助。
- ✅ **成功收到資料自動清除 `last_error`**：連線恢復後 fragment 自動切回圖表，不需使用者操作。
- ✅ **`4401/4409` 停止重連**：認證失效應停止並呈現錯誤；`4409` 在 Streamlit 單 session 架構下不應出現。
- ✅ **`self._thread` 儲存**：防止 `start()` 重複建立執行緒；供測試 21 `join()` 驗退出。
- ✅ **`loop.close()` 於 finally**：不論正常退出或例外均關閉 event loop，避免資源洩漏。
- ✅ **`early return` 而非 `st.stop()`**：`run_every` 繼續執行，連線恢復後自動切回圖表。
- ✅ **不傳 `cid`**：後端規格明定可選；Streamlit 無 `sessionStorage`。
- ✅ **`httpx.AsyncClient`（async）換票**：在 `asyncio.new_event_loop()` 的 async context 內不可用同步 `httpx.Client`。
- ✅ **`_state.get_token()` 而非裸讀 `session_state`**：使用模組存取層，隔離 key 字串耦合。
- ✅ **`monkeypatch.setenv("USE_MOCK", "false")` 觸發 api 路徑**：對齊 `conftest.py` 的 `autouse` 快取清除慣例，不需手動 `cache_clear()`。
