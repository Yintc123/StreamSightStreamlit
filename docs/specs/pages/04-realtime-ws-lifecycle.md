# 規格書：即時監控 WebSocket 連線生命週期（離開頁面 / session 結束自動斷聯）

> 狀態：**已實作**（核心測試 26–33 全綠；§6.2 app.py 切頁 hook 測試 34–35 為可選，未實作）／ 開發模式：**嚴格 TDD（見 `CLAUDE.md`）**
>
> **語言**：繁體中文。
>
> 🔗 延伸既有規格：[04-realtime-ws-client.md](./04-realtime-ws-client.md)（`RealtimeWsClient` 連線 / 重連 / 錯誤契約，測試 18–25）。本規格新增「連線釋放」機制與測試 **26–33**，不改動既有連線 / 重連 / 錯誤行為。

---

## 0. 問題陳述（為何需要這個機制）

目前 `pages/realtime_monitor.py` 進入頁面時建立 `RealtimeWsClient`（背景 daemon 執行緒 + WS 長連線），存入 `st.session_state["rt_ws_client"]`。**全專案沒有任何地方呼叫 `client.stop()`**，導致：

1. **切換到別頁後連線不斷**：`st.session_state` 跨頁面存活，背景執行緒持續運行、持續回 `pong`。
2. **關閉瀏覽器分頁後執行緒不退**：Streamlit server 為單一長命行程服務多 session；session 結束只回收 `session_state`，但背景 `while not stop.is_set()` 迴圈沒人設 stop，執行緒在 server 上**持續重連、持續回 pong**，直到 server 重啟。

### 0.1 後端事實（決定「連線會不會自己斷」）

> 來源：後端 `app/api/routers/ws/router.py`、`app/services/ws/manager.py`、`app/core/config/base.py` 與對應整合測試。

| 機制 | 預設 | 觸發條件 | close code |
|---|---|---|---|
| Missed-pong | 30s × 2 = **60s** | 連續 2 次 ping 未回 pong | `4000` |
| Idle timeout | **120s** | **無任何進站訊息**（含 pong） | `4000` |
| Reauth 複查 | **300s** | 帳號被封存 / 已登出（無 live token） | `4401` |
| Per-user 上限 | **10** | 同帳號 WS 連線數超過 | `1013`（拒新） |

**關鍵推論**：現行 client 的接收迴圈**會主動回 pong**（`_connect_and_subscribe` 的 `ping → pong` 分支）。切頁後背景執行緒**仍在回 pong** → idle timeout 與 missed-pong **永遠不會觸發** → 對一個**正常登入中**的使用者，後端**不會**自動收掉這條連線（唯一兜底是登出 / 封存後的 300s reauth）。

> 結論：**後端不會替我們清理這條殭屍連線**，前端必須主動斷。這正是本規格存在的理由。

### 0.2 Streamlit 1.50 的約束（決定「能用什麼機制斷」）

> 來源：`.venv` 內 `streamlit/runtime/*` 原始碼查證。

| 需求 | Streamlit 是否提供 | 結論 |
|---|---|---|
| session 結束 callback（`on_session_end`） | ❌ 無 public API；`AppSession.__del__` 存在但依賴 GC 時機，不可靠 | 不能用 |
| 「切頁前」hook / page-change 事件 | ❌ 無 | **「切換前主動斷聯」在 Streamlit 字面上不可實現** |
| `st.cache_resource` 存連線 | ⚠️ **跨 session 全域共享**、且逐出無 callback | **不可用**：多使用者會共用同一條 WS，A 登出會斷 B |
| `st.navigation` 切頁 → 整頁 rerun | ✅ 會，且清掉舊頁的 `run_every` fragment | **可用**：切頁後舊頁 fragment 會停止執行 |
| `@st.fragment(run_every=1.0)` 在整頁 rerun / session 結束後 | ✅ 停止排程 | **可用**：fragment 停止 = 一個可觀測的「離開」訊號 |

**設計上的硬約束**：既然沒有 session-end hook、也沒有切頁前 hook，就**無法在切頁 / 關分頁的那一刻同步斷線**。唯一橫跨「切頁 + 關分頁 + 崩潰」三種情境、且不碰 Streamlit 內部 API 的可觀測訊號，是「**負責每秒更新畫面的 fragment 是否還在跑**」。

---

## 1. 設計：Dead-man's switch（看門狗自動斷聯）

**核心想法**：讓「頁面是否還活著」變成一個背景執行緒可觀測的心跳。

- `live_panel` fragment 每次執行（每秒一次，**只在該頁被顯示時**）呼叫 `client.touch()`，更新 `_last_touch` 時戳。
- `RealtimeWsClient` 多啟一條**看門狗 daemon 執行緒**，每秒檢查：`now - _last_touch > IDLE_STOP_SECONDS` 即判定「頁面已離開或 session 已結束」→ 設 `stop` 事件 → 主動送 WS close 斷線 → 兩條執行緒退出。

**為何這一招同時解掉切頁與關分頁：**

| 情境 | fragment 是否續跑 | 結果 |
|---|---|---|
| 切換到別頁 | 整頁 rerun 清掉舊頁 fragment → **停** | `_last_touch` 凍結 → 看門狗 ~5s 內斷線 |
| 關閉分頁 / session 逾時 | ScriptRunner 停 → fragment **停** | 同上 |
| 瀏覽器崩潰 / 斷網 | rerun 停 → fragment **停** | 同上 |
| **停留在該頁** | fragment 每秒 touch | `_last_touch` 持續更新 → **不斷線**（正確） |
| 拖動閾值 slider（整頁 rerun） | fragment 短暫重建，gap ≪ 5s | 不誤斷（5s 裕度吸收） |

**主動斷聯的語義**：看門狗設 `stop` 後，接收迴圈 `return` → `async with websockets.connect(...)` context 退出 → **送出正規 close frame**。後端收到乾淨關閉即刻釋放該 per-user 連線槽（不必等 idle timeout）。這是真正的「主動斷」，而非丟著不管。

### 1.1 時間常數

```python
IDLE_STOP_SECONDS = 5.0    # 超過此秒數未被 touch → 判定離開 → 斷線
WATCHDOG_INTERVAL = 1.0    # 看門狗檢查週期
```

- fragment `run_every=1.0`；`IDLE_STOP_SECONDS=5.0` 容忍約 4 次漏拍（rerun 抖動、整頁 rerun 空窗），不誤斷。
- 斷線延遲上界 ≈ `IDLE_STOP_SECONDS + WATCHDOG_INTERVAL`（約 6s）；相對 per-user 上限 10 條，可忽略。
- 兩者為模組常數；`IDLE_STOP_SECONDS` 亦作為 `RealtimeWsClient` 建構參數（預設值），供測試注入極小值（如 `0.2`）。

---

## 2. `lib/realtime_ws.py`：改動（在既有基礎上新增，不改連線 / 重連邏輯）

### 2.1 模組層級新增

```python
import time   # 既有 import 區塊補入

IDLE_STOP_SECONDS = 5.0
WATCHDOG_INTERVAL = 1.0


def _run_watchdog(
    seconds_since_touch: Callable[[], float],
    idle_stop: float,
    interval: float,
    stop: threading.Event,
) -> None:
    """看門狗執行緒：每 interval 秒檢查閒置；超過 idle_stop 未被 touch → 設 stop。

    stop.wait(timeout) 回傳 True（stop 已被設，含外部 stop()）即退出；False（逾時）則續查。
    設 stop 後：中斷 backoff 等待、讓接收迴圈 return（送 WS close）、終止重連 while。
    """
    while not stop.wait(timeout=interval):
        if seconds_since_touch() > idle_stop:
            stop.set()
            return
```

> `_run_watchdog` 為**模組層級函式**（對齊 `_run_with_reconnect` 風格），測試可獨立驗證、必要時 monkeypatch。
>
> **檢查週期 `interval` 由 `start()` 傳入 `min(WATCHDOG_INTERVAL, idle_stop)`**，非直接吃固定常數：
> - 正式環境 `idle_stop=5.0` → `interval = min(1.0, 5.0) = 1.0`，行為與「固定 1s」完全相同（延遲上界仍 ~6s）。
> - 測試注入小 `idle_stop`（如 `0.2`）→ `interval=0.2`，確保檢查週期不粗於閒置窗，測試快速收斂、不空等 1s。

### 2.2 `RealtimeWsClient` 新增成員與方法

```python
def __init__(self, *, http_base, ws_base, get_token, idle_stop_seconds: float = IDLE_STOP_SECONDS):
    ...
    self._idle_stop = idle_stop_seconds
    self._last_touch = time.monotonic()          # 建構即給初值，避免 start 前誤判
    self._watchdog: threading.Thread | None = None
```

```python
def touch(self) -> None:
    """由 live_panel fragment 每次執行時呼叫；更新心跳時戳（thread-safe）。"""
    with self._lock:
        self._last_touch = time.monotonic()

def _seconds_since_touch(self) -> float:
    with self._lock:
        return time.monotonic() - self._last_touch

def is_alive(self) -> bool:
    """連線執行緒仍運行且未被要求停止 → True。供頁面判斷是否需重建 client。"""
    return (
        self._thread is not None
        and self._thread.is_alive()
        and not self._stop.is_set()
    )
```

### 2.3 `start()`：同時啟動連線執行緒與看門狗

```python
def start(self) -> None:
    """啟動連線 daemon 執行緒 + 看門狗執行緒；執行緒仍活著則 no-op（防重複）。"""
    if self._thread is not None and self._thread.is_alive():
        return
    self._last_touch = time.monotonic()          # 重置心跳，避免啟動瞬間誤判閒置
    self._thread = threading.Thread(target=_run_with_reconnect, args=(...), daemon=True)
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
```

> `stop()` **不變**（`self._stop.set()`）：同一 `stop` 事件即可終止連線執行緒與看門狗；`_run_watchdog` 的 `stop.wait()` 立即回 True 退出。

### 2.4 接收迴圈：`stop` 已被檢查，無需改動

`_connect_and_subscribe` 既有 `async for raw in ws: if stop.is_set(): return`。看門狗設 stop 後，後端資料 / ping 每秒到達使迴圈於 ~1s 內喚醒並 `return`，context 退出送 close frame。**本規格不改此函式。**

> 補強（可選）：若擔心斷線期間後端剛好無訊息使 `async for` 遲遲不喚醒，可將 recv 改為 `await asyncio.wait_for(ws.recv(), timeout=1.0)` 並在 `TimeoutError` 時 `continue`。因 `realtime.stream` 穩定每秒推送，**預設不採用**，列為未來優化。

---

## 3. `pages/realtime_monitor.py`：改動

### 3.1 建立 / 重建 client 的守衛（處理「斷線後重回頁面」）

看門狗停掉 client 後，`rt_ws_client` 物件仍留在 `session_state`。使用者重回本頁時，**不可重用已死的 client**（其執行緒已退出、不會再收資料）。改用 `needs_new_client` 判斷是否重建：

```python
# lib/realtime_ws.py 新增純函式（決策抽到 lib，頁面保持薄、可單元測試）
def needs_new_client(existing: "RealtimeWsClient | None", use_mock: bool) -> bool:
    """api 模式下，client 不存在或已停止 → 需要建立新的。"""
    return (not use_mock) and (existing is None or not existing.is_alive())
```

頁面初始化區塊改為：

```python
_existing = st.session_state.get("rt_ws_client")
if needs_new_client(_existing, settings.use_mock):
    _tok = _state.get_token() or ""
    _ws_init = RealtimeWsClient(
        http_base=settings.fastapi_base_url,
        ws_base=settings.fastapi_ws_url,
        get_token=lambda: _tok,
    )
    _ws_init.start()
    st.session_state["rt_ws_client"] = _ws_init   # 覆蓋舊的（含已死的）
```

> 重回頁面若舊 client 已死 → 建立**新連線**（buffer 從頭累積，屬預期）。
> 停留頁面的整頁 rerun（如拖 slider）→ 舊 client `is_alive()` 為真 → **重用**，不重連。

### 3.2 `live_panel()`：每次執行呼叫 `touch()`

在取得 `_ws` 之後、`last_error` 判斷**之前**呼叫（確保連線異常期間心跳仍在，看門狗不因 error 早退而誤斷）：

```python
@st.fragment(run_every=1.0)
def live_panel() -> None:
    if not settings.use_mock:
        _ws: RealtimeWsClient = st.session_state["rt_ws_client"]
        _ws.touch()                       # ← 心跳：宣告「本頁仍在顯示」
        if _ws.last_error:
            st.error(_ws.last_error)
            return
        buffer = _ws.buffer
    else:
        buffer = st.session_state["rt_buffer"]
    # …以下渲染與 mock 生成完全不變…
```

---

## 4. session_state 契約（本規格不新增 key）

| Key | 變化 | 說明 |
|---|---|---|
| `rt_ws_client` | 生命週期語義更新 | 由 `needs_new_client` 守衛：不存在 / 已死 → 重建；活著 → 重用。看門狗停掉後物件仍在，`is_alive()=False` 觸發下次重建 |

`rt_buffer` / `rt_tick` / `rt_threshold` 不變。

---

## 5. 邊界情境彙整

| 情境 | 行為 |
|---|---|
| 停留即時監控頁 | fragment 每秒 touch → 不斷線 |
| 切到別頁 | fragment 停 → 看門狗 ~5s 內送 WS close 斷線、執行緒退出；後端即刻釋放連線槽 |
| 別頁待一陣後回來 | 舊 client 已死 → `needs_new_client=True` → 建新連線 |
| 快速切走又切回（< 5s） | 看門狗可能尚未斷；回來時 `is_alive()` 仍真 → **重用舊連線**（無縫，不重連） |
| 關閉分頁 / session 逾時 | fragment 停 → 看門狗 ~5s 內斷線、**server 端執行緒退出**（解決殭屍執行緒累積） |
| 連線 error / backoff 中離開 | 看門狗設 stop → `stop.wait(timeout)` 立即返回 → 中斷 backoff → 執行緒退出 |
| `use_mock=True` | 不建立 client、無看門狗、`live_panel` 不 touch |

---

## 6. 備選方案（已評估，未採用 / 列為可選）

### 6.1 ✅（採用）看門狗 dead-man's switch — 見 §1

唯一橫跨切頁 + 關分頁 + 崩潰、零跨頁耦合、不碰 Streamlit 內部 API。**設為核心且必要**——因為關分頁 / 崩潰**沒有任何 Streamlit hook**，只有看門狗能解 server 端執行緒洩漏。

### 6.2 🔸（可選加強）app.py 偵測切頁 → 立即斷

`st.navigation(pages)` 回傳當前 `StreamlitPage`，每次**整頁 rerun**（含切頁）都會在 `app.py` 執行。可比對前後 `page.url_path`，離開即時監控頁時**立刻** `stop()`：

```python
# app.py：st.navigation(pages).run() 拆成兩步
selected = st.navigation(pages)
release_ws_if_left_monitor(st.session_state, selected.url_path)   # lib/realtime_ws.py 純函式
selected.run()
```

```python
def release_ws_if_left_monitor(session_state, current_url_path: str) -> bool:
    """離開即時監控頁（url_path="realtime_monitor"）時 stop 並移除 WS client。"""
    prev = session_state.get("_active_url_path")
    session_state["_active_url_path"] = current_url_path
    client = session_state.get("rt_ws_client")
    if prev == "realtime_monitor" and current_url_path != "realtime_monitor" and client is not None:
        client.stop()
        del session_state["rt_ws_client"]
        return True
    return False
```

| 面向 | 效果 |
|---|---|
| 優點 | 切頁**0 延遲**釋放連線槽；對「切頁」情境是確定性斷線（防禦縱深） |
| 缺點 | app.py 產生跨頁耦合；**快速切走又切回會多一次重連**（buffer 重置）；**無法涵蓋關分頁**（該情境 app.py 根本不執行） |
| 取捨 | 看門狗已把切頁延遲壓到 ~5s；per-user 上限 10 條下，0s vs 5s 差異無實質意義 |

**建議**：先只做 §1 看門狗（較簡潔、快速往返無縫、單一機制覆蓋全部）。**僅當**營運上出現 per-user 連線槽壓力、需要 0 延遲釋放時，再加此 hook。本規格的測試計畫 34–35 為此可選項，標記為 optional。

### 6.3 ❌（不可用）`st.cache_resource` 存連線

跨 session 全域共享 → 多使用者共用一條 WS，A 登出斷 B；逐出無 callback → 無法在清理時關 WS。**直接排除。**

### 6.4 ❌（不可用）依賴 session-end callback / `__del__`

Streamlit 1.50 無 public session-end hook；`AppSession.__del__` 依賴 GC 時機（可能延遲數秒至數分）、多執行緒下行為未定義。**不可靠，排除。**

---

## 7. TDD 測試計畫（26–33 核心；34–35 可選）

> 延續 `04-realtime-ws-client.md` 測試 18–25；編號接續。
> `tests/conftest.py` 的 `autouse` fixture 已在每測試前 `get_settings.cache_clear()` 並設 `APP_ENV=test`（`use_mock=True`）。

### 7.1 Unit — `tests/unit/test_realtime_ws.py`

**共用 helper（沿用既有 `_client()`；新增可帶 idle_stop 的變體）**：

```python
def _client(idle_stop=5.0):
    return RealtimeWsClient(
        http_base="http://x", ws_base="ws://x",
        get_token=lambda: "t", idle_stop_seconds=idle_stop,
    )
```

#### 26. `touch()` 更新心跳，`_seconds_since_touch()` 隨之歸零

```python
import time

def test_touch_resets_seconds_since_touch():
    c = _client()
    time.sleep(0.05)
    assert c._seconds_since_touch() >= 0.05
    c.touch()
    assert c._seconds_since_touch() < 0.05
```

#### 27. `is_alive()`：start 前 False、start 後 True、stop 後 False

```python
import lib.realtime_ws as _ws_module

def test_is_alive_lifecycle(monkeypatch):
    async def _idle(*_a, **_k):     # 連上後靜候 stop，不真連後端
        while True:
            await asyncio.sleep(0.05)
    monkeypatch.setattr(_ws_module, "_connect_and_subscribe", _idle)

    c = _client()
    assert c.is_alive() is False          # 未 start
    c.start()
    assert c.is_alive() is True           # 執行中
    c.stop()
    c._thread.join(timeout=2.0)
    assert c.is_alive() is False          # 已停
```

#### 28. 看門狗：閒置超過 `idle_stop` → 自動設 stop、執行緒退出

```python
def test_watchdog_stops_when_idle(monkeypatch):
    """不呼叫 touch，看門狗應在 idle_stop 後設 stop 並讓執行緒退出。"""
    async def _idle(*_a, **_k):
        while True:
            await asyncio.sleep(0.02)
    monkeypatch.setattr(_ws_module, "_connect_and_subscribe", _idle)

    c = _client(idle_stop=0.2)
    c.start()                             # start 重置 _last_touch
    c._thread.join(timeout=3.0)           # 不再 touch → ~0.2s 後被看門狗停掉
    assert not c._thread.is_alive()
    assert c._stop.is_set()
```

#### 29. 看門狗：持續 `touch()` 期間**不**斷線；停止 touch 後才斷

```python
def test_watchdog_keeps_alive_while_touched(monkeypatch):
    async def _idle(*_a, **_k):
        while True:
            await asyncio.sleep(0.02)
    monkeypatch.setattr(_ws_module, "_connect_and_subscribe", _idle)

    c = _client(idle_stop=0.3)
    c.start()
    for _ in range(6):                    # 0.6s 內每 0.1s touch 一次（< idle_stop）
        time.sleep(0.1)
        c.touch()
    assert c.is_alive() is True           # 持續心跳 → 仍活著

    c._thread.join(timeout=3.0)           # 停止 touch → 看門狗於 ~0.3s 後停掉
    assert not c._thread.is_alive()
```

#### 30. 看門狗中斷 backoff：連線失敗退避中離開，應快速退出

```python
def test_watchdog_interrupts_backoff(monkeypatch):
    """_connect 一直失敗（進入 backoff），閒置達標時看門狗仍能讓執行緒 < 2s 退出。"""
    async def _always_fail(*_a, **_k):
        raise Exception("強制失敗，觸發 backoff")
    monkeypatch.setattr(_ws_module, "_connect_and_subscribe", _always_fail)

    c = _client(idle_stop=0.2)
    c.start()
    c._thread.join(timeout=2.0)
    assert not c._thread.is_alive()       # 看門狗設 stop → stop.wait 立即返回 → 退出
```

#### 31. `needs_new_client` 決策純函式

```python
from lib.realtime_ws import needs_new_client

def test_needs_new_client_mock_never():
    assert needs_new_client(None, use_mock=True) is False

def test_needs_new_client_none_in_api():
    assert needs_new_client(None, use_mock=False) is True

def test_needs_new_client_reuses_alive(monkeypatch):
    async def _idle(*_a, **_k):
        while True:
            await asyncio.sleep(0.05)
    monkeypatch.setattr(_ws_module, "_connect_and_subscribe", _idle)
    c = _client(); c.start()
    assert needs_new_client(c, use_mock=False) is False   # 活著 → 重用
    c.stop(); c._thread.join(timeout=2.0)
    assert needs_new_client(c, use_mock=False) is True     # 已死 → 重建
```

### 7.2 頁面行為 — `tests/app/test_realtime_monitor.py`（AppTest）

> `_MockWsClient` 擴充：新增 `touch()`（計數）與 `is_alive()`（回傳可控旗標）。

```python
class _MockWsClient:
    def __init__(self, buffer=None, last_error=None, alive=True):
        self._buf = buffer or []
        self.last_error = last_error
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
```

#### 32. `live_panel` 每次 render 呼叫 `touch()`（心跳存在）

```python
def test_live_panel_touches_client(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "false")
    mock = _MockWsClient(buffer=[Reading(ts=_NOW, value=42.0)], alive=True)
    at = _open_monitor(Actor("alice", "admin", grade=AdminRole.VIEWER), rt_ws_client=mock)
    assert not at.exception
    assert mock.touch_count >= 1          # 至少一次心跳
```

#### 33. 注入「已死」client → 頁面重建新 client（不重用）

> 透過 `needs_new_client` 守衛：注入 `is_alive()=False` 的 mock，頁面應建立新的 client。
>
> **patch 目標為來源模組 `lib.realtime_ws.RealtimeWsClient`，非 `pages.realtime_monitor.RealtimeWsClient`**：頁面的 `from lib.realtime_ws import RealtimeWsClient` 於每次 `at.run()` 會 re-exec，patch 頁面命名空間會被該 import 覆蓋；必須 patch 來源，讓 re-exec 的 import 取到 spy。用 `_open_monitor_api`（use_mock=False 路徑）。

```python
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
```

### 7.3（可選）§6.2 app.py 切頁 hook — 測試 34–35

> 僅在採用 §6.2 時實作。

#### 34.（unit）`release_ws_if_left_monitor`：離開即時監控頁 → stop + 移除

```python
def test_release_on_leaving_monitor():
    ss = {"_active_url_path": "realtime_monitor", "rt_ws_client": _MockWsClient()}
    client = ss["rt_ws_client"]
    assert release_ws_if_left_monitor(ss, "analytics") is True
    assert client.stopped is True
    assert "rt_ws_client" not in ss

def test_no_release_when_staying():
    ss = {"_active_url_path": "realtime_monitor", "rt_ws_client": _MockWsClient()}
    assert release_ws_if_left_monitor(ss, "realtime_monitor") is False
    assert "rt_ws_client" in ss
```

#### 35.（app）切頁後即時監控 client 被 stop（AppTest `switch_page`）

---

## 8. 實作順序（TDD 里程碑）

依 `CLAUDE.md` Red→Green→Refactor，一測試一小步：

1. **`touch()` / `_seconds_since_touch()`**（測試 26 先紅 → 補方法 → 綠）
2. **`is_alive()`**（測試 27）
3. **`_run_watchdog` + `start()` 啟看門狗**（測試 28 → 29 → 30）
4. **`needs_new_client`**（測試 31）
5. **`pages/realtime_monitor.py`**：守衛改用 `needs_new_client`、`live_panel` 加 `touch()`（AppTest 32 → 33）
6. **全套 `pytest` 通過**，含既有 1–25
7. （可選）§6.2 app.py hook（測試 34 → 35）

---

## 9. 已定案決策

- ✅ **看門狗 dead-man's switch 為核心機制**：唯一同時涵蓋切頁 / 關分頁 / 崩潰、且不碰 Streamlit 內部 API；也是唯一能解 server 端殭屍執行緒累積的手段。
- ✅ **心跳來源為 `live_panel` fragment 的 `touch()`**：fragment 「是否還在跑」正好等價於「頁面是否還被顯示」，是 Streamlit 下最可靠的離開訊號。
- ✅ **`IDLE_STOP_SECONDS=5.0`**：容忍 ~4 次 fragment 漏拍，不誤斷；斷線延遲上界 ~6s，相對 per-user 上限 10 可忽略。
- ✅ **看門狗檢查週期 = `min(WATCHDOG_INTERVAL, idle_stop)`**（非固定常數）：正式 `idle_stop=5.0` → `1.0`，行為與固定 1s 相同；測試小 `idle_stop`（0.2）→ 檢查週期同步縮小，測試快速收斂且不粗於閒置窗。`_run_watchdog` 因此多收一個 `interval` 參數（4 參）。
- ✅ **同一 `stop` 事件驅動連線執行緒與看門狗**：`stop.wait()` 立即中斷 backoff / 接收迴圈，乾淨退出。
- ✅ **主動送 WS close frame**（context 退出）：後端即刻釋放連線槽，非丟棄等 timeout。
- ✅ **`needs_new_client` 守衛 + `is_alive()`**：斷線後重回頁面重建新連線；停留頁面的整頁 rerun 重用舊連線不重連。
- ✅ **決策邏輯抽到 `lib/` 純函式**（`needs_new_client` / 可選 `release_ws_if_left_monitor`）：頁面保持薄、可單元測試（對齊 `CLAUDE.md`）。
- 🔸 **app.py 切頁 hook 列為可選加強**：0 延遲釋放但帶跨頁耦合與快速往返重連成本；預設不做，視 per-user 槽壓力再加。
- ❌ **不用 `st.cache_resource`**（跨 session 共享、無逐出 callback）／**不依賴 session-end callback / `__del__`**（無 public API、GC 時機不可靠）。
