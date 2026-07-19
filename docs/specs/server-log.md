# Server Log 接入規格

> **頁面**：`pages/system_management.py`（日誌 / DB 狀態分頁）
> **目標**：將 Phase 1 靜態 mock 替換為真實後端 `/monitoring/*` API 呼叫。
>
> ⚠️ **範圍調整（2026-07-19）**：本規格的 **DB 狀態部分已被取代**——DB 狀態分頁
> 改接 `GET /monitoring/infra`（CPU / 記憶體 / 連線數 + 每 1 秒 fragment 輪詢），
> 權威定義見 [06-admin.md](pages/06-admin.md)。因此 §2.3 `DbStatus`、§3.1 的
> `get_db_status` / `get_db_history`、§4.3 `seed_db_status()`、§5.3 DB 狀態 UI、
> §8 Phase 1 測試 7 / 9 與 Phase 2 測試 13–14 **不實作**。
> 日誌部分（LogEntry / get_logs / cursor 分頁）仍以本文為單一真相，已實作完成。

---

## 1. 現況與差距分析

### 1.1 後端已有端點

後端 `GET /monitoring/logs`、`GET /monitoring/db`、`GET /monitoring/db/history` 均已實作完整。

| 端點 | 回應型別 | 欄位 | 權限 |
|---|---|---|---|
| `GET /monitoring/logs` | `Page[LogEntry]` | `ts, level, logger, message, request_id, module, func, line` | SUPER_ADMIN |
| `GET /monitoring/db` | `DbSample` | `ts, pool, connections, db_size_bytes, longest_query_seconds, backend` | VIEWER |
| `GET /monitoring/db/history` | `DbHistoryResponse` | `snapshots: list[DbSample]` | 任一 admin |

**日誌類型**：後端記錄的是 Python `logging` 基礎設施日誌（logger 名稱、模組、函式），而非商業動作審計日誌。這是「伺服器日誌」的正確定義，Streamlit 端需對齊此 schema。

### 1.2 Streamlit Mock 現況

| 面向 | Mock（Phase 1） | 後端 API |
|---|---|---|
| 日誌欄位 | `time(str), user, action, result, level` | `ts(epoch ms), level, logger, message, request_id` |
| 日誌分頁 | page-based 頁碼（`admin_log_page`） | cursor-based（`cursor, limit`） |
| DB 欄位 | `connected(bool), total_rows(int), size_bytes(int)` | `pool{}, connections{}, db_size_bytes(int)` |
| DB 連線判斷 | `connected: bool` | 以 `pool["checked_out"]` 或 HTTP 成功隱含 |

### 1.3 規格調整決策

1. **日誌欄位**：顯示欄調整為 `時間 / 等級 / 模組 / 訊息 / Request ID`；移除 mock 專用的 `user / action / result`。
2. **端點路徑**：規格 §API Endpoints 的 `/admin/logs` 更正為 `/monitoring/logs`（本文為權威定義）。
3. **分頁策略**：改 cursor-based，UI 以「上一頁 / 下一頁」按鈕 + cursor stack 實作。
4. **DB 狀態**：連線狀態由 `pool.size > 0` 推斷，不新增 `connected` 布林欄；改顯示 `pool.size, pool.checked_out, db_size_bytes`。
5. **時間轉換**：`date` 選擇器 → `date_range_to_ms()` → `since_ms / until_ms`（epoch ms）。

---

## 2. 資料契約（lib/models.py 新增）

### 2.1 LogEntry

```python
@dataclass
class LogEntry:
    ts: int               # epoch ms（UTC）
    level: str            # "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
    logger: str           # Python logger name
    message: str
    request_id: str | None = None
    module: str | None = None
    func: str | None = None
    line: int | None = None
```

### 2.2 LogsPage

```python
@dataclass
class LogsPage:
    items: list           # List[LogEntry]
    next_cursor: str | None = None
```

### 2.3 DbStatus（對應 monitoring.LogEntry → DbSample）

```python
@dataclass
class DbStatus:
    ts: int
    pool_size: int              # pool["size"]
    pool_checked_out: int       # pool["checked_out"]
    active_connections: int     # connections["active"]
    db_size_bytes: int | None = None
    longest_query_seconds: float | None = None
    backend: str = "unknown"
```

---

## 3. API 方法（lib/api_client.py 擴充）

`DataSource` Protocol 只涵蓋 records CRUD（user-facing）。Admin 監控操作**不加入** `DataSource` Protocol，直接掛在 `ApiDataSource` 上。

### 3.1 新增方法

```python
class ApiDataSource:
    # —— 既有 records 方法略 ——

    def get_logs(
        self,
        level: str | None = None,
        since_ms: int | None = None,
        until_ms: int | None = None,
        logger_name: str | None = None,
        request_id: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> LogsPage: ...
    # → GET /monitoring/logs?level=&since=&until=&logger=&request_id=&cursor=&limit=
    # → LogsPage(items=[LogEntry(...)], next_cursor=str|None)

    def get_db_status(self) -> DbStatus: ...
    # → GET /monitoring/db
    # → DbStatus(ts, pool_size, pool_checked_out, active_connections, db_size_bytes, ...)

    def get_db_history(
        self,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> list:  # list[DbStatus]
    # → GET /monitoring/db/history?start_ms=&end_ms=
    # → list[DbStatus]（由舊到新）
```

### 3.2 後端回應 → DbStatus 映射

```
DbSample.pool["size"]         → DbStatus.pool_size
DbSample.pool["checked_out"]  → DbStatus.pool_checked_out
DbSample.connections["active"] → DbStatus.active_connections（鍵不存在時預設 0）
DbSample.db_size_bytes        → DbStatus.db_size_bytes
DbSample.longest_query_seconds→ DbStatus.longest_query_seconds
DbSample.backend              → DbStatus.backend
```

---

## 4. lib/system_management.py 純函式擴充

所有函式無 Streamlit 依賴，可直接單元測試。

### 4.1 新增純函式

| 函式 | 簽章 | 契約 |
|---|---|---|
| `format_log_ts` | `(ts_ms: int) -> str` | epoch ms → `"YYYY-MM-DD HH:MM:SS"` UTC 字串 |
| `date_to_epoch_ms` | `(d: date) -> int` | date → UTC midnight epoch ms |
| `date_range_to_ms` | `(d_from: date, d_to: date) -> tuple[int, int]` | → `(since_ms, until_ms)`；until = d_to 當日 23:59:59.999 |
| `log_entries_to_rows` | `(entries: list) -> list[dict]` | `LogEntry list → [{"時間":..., "等級":..., "模組":..., "訊息":..., "Request ID":...}]`；供 `st.dataframe` 使用 |
| `db_status_to_metrics` | `(status: DbStatus) -> list` | `DbStatus → [Metric(...), ...]`；供 `metric_cards()` 使用 |

### 4.2 seed_logs() 更新

`seed_logs()` 返回 `list[LogEntry]`（對齊後端 schema），不再返回舊 dict 格式。

```python
def seed_logs() -> list:  # list[LogEntry]
    """mock 靜態日誌，格式對齊後端 LogEntry schema。決定性，不依賴時鐘。"""
    return [
        LogEntry(ts=1704067200000, level="INFO",    logger="app.api.routers.auth",    message="login success",            request_id="req-001"),
        LogEntry(ts=1704070800000, level="INFO",    logger="app.services.record",     message="record created id=42",     request_id="req-002"),
        LogEntry(ts=1704074400000, level="WARNING", logger="app.core.auth.jwt",       message="token near expiry",        request_id="req-003"),
        LogEntry(ts=1704078000000, level="WARNING", logger="app.services.monitoring", message="log flush failed, retry",  request_id=None),
        LogEntry(ts=1704081600000, level="ERROR",   logger="app.core.db.session",     message="db connection pool exhausted", request_id="req-005", module="session", func="get_session", line=42),
    ]
```

### 4.3 seed_db_status() 更新

```python
def seed_db_status() -> DbStatus:
    return DbStatus(
        ts=1704067200000,
        pool_size=5,
        pool_checked_out=2,
        active_connections=2,
        db_size_bytes=52_428_800,   # 50 MB
        longest_query_seconds=0.012,
        backend="mariadb",
    )
```

---

## 5. pages/system_management.py 更新

### 5.1 資料載入策略

```python
from lib.config import get_settings
from lib.system_management import seed_logs, seed_db_status

settings = get_settings()
if settings.use_mock:
    log_page = LogsPage(items=seed_logs(), next_cursor=None)
    db = seed_db_status()
else:
    # 複用 lib/data_source._get_api_client()（process-level 共用 ApiClient）
    ds = ApiDataSource(_get_api_client(), settings.fastapi_base_url)
    log_page = ds.get_logs(
        level=level_filter or None,
        since_ms=since_ms,
        until_ms=until_ms,
        cursor=cursor,
        limit=100,
    )
    db = ds.get_db_status()
```

### 5.2 日誌分頁 UI

```
[ 日誌 ] [ DB 狀態 ]

── 日誌 ─────────────────────────────────────────
等級 [全部▾]    時間範圍 [起始日期] ~ [結束日期]

時間                等級     模組              訊息                    Request ID
─────────────────────────────────────────────────────────────────────────────
2024-01-01 08:00  INFO     auth.router       login success           req-001
2024-01-01 09:00  WARNING  core.auth.jwt     token near expiry       req-003
2024-01-01 10:00  ERROR    core.db.session   pool exhausted          req-005

                                              [ ← 上一頁 ]  [ 下一頁 → ]
```

**呈現**：`st.dataframe(log_entries_to_rows(...), hide_index=True)`，上方
`st.caption("時間為 UTC")`；不使用 `st.columns` 手排表格。

**分頁（cursor-based）**：
- `st.session_state["admin_log_cursor"]`：當前游標（`None` = 第一頁）
- `st.session_state["admin_log_cursor_stack"]`：`list[str | None]`，回上頁用的游標棧（第一頁的游標為 `None`，push 後棧內可能含 `None`）
- 「下一頁」：push 當前游標入棧，設 cursor = `log_page.next_cursor`
- 「上一頁」：pop 棧頂，設 cursor = 棧頂值
- `log_page.next_cursor is None` → 禁用「下一頁」按鈕

### 5.3 DB 狀態分頁 UI

```
── DB 狀態 ──────────────────────────────────────
┌──────────────┬─────────────────┬──────────────┐
│ 連線池大小    │ 使用中連線      │ DB 大小       │
│      5       │       2         │   50.0 MB    │
└──────────────┴─────────────────┴──────────────┘

後端類型: mariadb   最長查詢: 0.012s

即時資料歷史查詢:
[起始日期] ~ [結束日期]  [查詢]
─────────────────────────
  ts            pool_size  checked_out  db_size_bytes
  ...
```

`metric_cards()` 傳入 `db_status_to_metrics(db)` 回傳的 `list[Metric]`。

---

## 6. session_state 契約（增補）

| Key | 前綴 | 說明 |
|---|---|---|
| `admin_log_category` | `admin_log_` | 等級篩選（由 `filter_bar` 管理；`filter_bar` 的 key 命名慣例為 `{prefix}_category`） |
| `admin_log_date_from` | `admin_log_` | 日誌分頁起始日期 |
| `admin_log_date_to` | `admin_log_` | 日誌分頁結束日期 |
| `admin_log_cursor` | `admin_log_` | 當前頁游標（None = 第一頁） |
| `admin_log_cursor_stack` | `admin_log_` | list[str]，上一頁游標棧 |

> 等級 / 日期篩選任一改變時，重設 `admin_log_cursor = None` 且清空 `admin_log_cursor_stack`（避免舊游標混用）。

---

## 7. 錯誤處理

| 情境 | 呈現（依 error-handling.md §3） |
|---|---|
| `get_logs()` 失敗 | `render_error(e)` + `empty_state("無法載入日誌")` |
| `get_db_status()` 失敗 | `render_error(e)` + `empty_state("無法取得 DB 狀態")` |
| `get_db_history()` 失敗 | `render_error(e)` + `empty_state("無法取得歷史資料")` |
| 篩選後無資料 | `empty_state("無符合條件的日誌")` |

---

## 8. TDD 計畫（Red → Green → Refactor）

### Phase 1 — 純函式 unit tests（`tests/unit/test_system_management.py`）

| # | 測試描述 | 目標函式 |
|---|---|---|
| 1 | `format_log_ts(1704067200000)` → `"2024-01-01 00:00:00"` | `format_log_ts` |
| 2 | `format_log_ts(0)` → `"1970-01-01 00:00:00"` | `format_log_ts` |
| 3 | `date_to_epoch_ms(date(2024, 1, 1))` → `1704067200000` | `date_to_epoch_ms` |
| 4 | `date_range_to_ms(date(2024,1,1), date(2024,1,1))` → since < until，差值 = 86399999 | `date_range_to_ms` |
| 5 | `log_entries_to_rows([LogEntry(...)])` → dict 含 `"時間", "等級", "模組", "訊息", "Request ID"` | `log_entries_to_rows` |
| 6 | `log_entries_to_rows([])` → `[]` | `log_entries_to_rows` |
| 7 | `db_status_to_metrics(seed_db_status())` → list 長度 3，第三項 value = `"50.0 MB"` | `db_status_to_metrics` |
| 8 | `seed_logs()` → list of `LogEntry`，各項 `level` 在合法集合內 | `seed_logs` |
| 9 | `seed_db_status()` → `DbStatus`，`db_size_bytes = 52428800` | `seed_db_status` |

### Phase 2 — api_client unit tests（`tests/unit/test_api_client.py`，MockTransport）

| # | 測試描述 |
|---|---|
| 10 | `get_logs()` → `GET /monitoring/logs`，回傳 `LogsPage` 含正確 `next_cursor` |
| 11 | `get_logs(level="ERROR", since_ms=1000, until_ms=2000)` → query 含 `level=ERROR&since=1000&until=2000` |
| 12 | `get_logs(cursor="123-0")` → query 含 `cursor=123-0` |
| 13 | `get_db_status()` → `GET /monitoring/db`，回傳 `DbStatus`；`pool["checked_out"]=2` → `pool_checked_out=2` |
| 14 | `get_db_history(start_ms=0, end_ms=1000)` → `GET /monitoring/db/history?start_ms=0&end_ms=1000` → `list[DbStatus]` |
| 15 | `get_logs()` 後端回 500 → 拋 `ApiError` |

### Phase 3 — 頁面行為 AppTest（`tests/app/test_system_management.py`）

| # | 測試描述 |
|---|---|
| 16 | mock 模式 → 日誌分頁顯示 `LogEntry` 欄位（「等級」「模組」「訊息」可在 dataframe 找到） |
| 17 | mock 模式 → 日誌分頁「下一頁」按鈕在 `next_cursor=None` 時禁用 |
| 18 | mock 模式 + 等級篩選 `WARNING` → 只顯示 WARNING / ERROR（視篩選邏輯） |
| 19 | mock 模式 → DB 狀態分頁顯示 metric_cards（連線池大小、使用中連線、DB 大小） |
| 20 | mock 模式 → 日期篩選改變後 `admin_log_cursor` 重設為 `None` |

---

## 9. 不在本規格範圍內

- **審計日誌（audit log）**：記錄「誰做了什麼動作、結果為何」的業務事件。若日後需要，應在後端新增獨立的 audit log 模型與端點，不混入 monitoring log。
- **Infra 指標圖表**（`GET /monitoring/infra`）：留給日後 realtime_monitor 頁整合。
- **WS 即時日誌推送**：本規格採 polling（頁面重整 / 手動），SSE/WS 為後續演進。

---

## 10. 依賴 / 備註

- 後端 `/monitoring/logs` 需 **SUPER_ADMIN**（grade ≥ 100），Streamlit 頁面已由 `build_pages(actor)` 限制——無需在頁面內重複檢查。
- `seed_logs()` / `seed_db_status()` 返回 `LogEntry` / `DbStatus` 物件（非 dict），統一型別，頁面透過純函式轉換為 display rows，mock 與 api 模式走同一渲染路徑。
- 時區：後端 `ts` 為 epoch ms（UTC）；`format_log_ts` 輸出 UTC，UI 加「(UTC)」標注。
- cursor stack 純 session_state 前端狀態，不需後端感知。
- `ApiDataSource.get_logs()` 已透過 `ApiClient._request("GET", ...)` 繼承重試、Bearer token 刷新、X-Request-ID 等通用行為。
