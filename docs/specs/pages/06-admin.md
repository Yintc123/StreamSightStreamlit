# 頁面規格:系統管理

- 頁面編號:6
- 對應模組:模組 5 系統管理
- 存取權限:**僅 `grade >= AdminRole.SUPER_ADMIN`（≥100，含 ROOT=999）**（`editor` / `viewer` 不可見；由 `build_pages(actor)` 動態不註冊，比隱藏連結更安全）。存取軸的權威定義見[前端頁面結構 §存取控制](../frontend-pages.md#存取控制本節為存取軸的單一真相)。
- 導覽:`build_pages(actor)` 僅在 `actor.grade >= AdminRole.SUPER_ADMIN` 時追加此頁——見[應用骨架 §5](../app-skeleton.md#5-導覽與頁面註冊build_pages)
- 相關:[UI Helper 規格](../ui.md)、[錯誤處理規格](../error-handling.md)

## 目的

提供 Admin 查閱系統日誌與伺服器狀態（CPU / 記憶體 / DB 連線數）。

> **管理員管理功能已移至主前端（Next.js CMS）實作**，Streamlit 端不再提供此分頁。

## 版面

以 `st.tabs` 分為兩個分頁:日誌 / DB 狀態。

## UI 版面規劃

寬版，`st.tabs(["日誌", "DB 狀態"])`。兩分頁皆唯讀。

```
[ 日誌 ] [ DB 狀態 ]                                         ← st.tabs

── 日誌 ────────────────────────────────────────────────
 等級[▾]  時間範圍              ← filter_bar(key_prefix="admin_log")
 時間  等級  模組  訊息  Request ID   ← st.dataframe(log_entries_to_rows(...))
                       [ ← 上一頁 ]  [ 下一頁 → ]   ← cursor-based 分頁

── DB 狀態 ──────────────────────────────────────────────
 ┌──────────────┬──────────────┬──────────────┐
 │  CPU 佔用率   │  記憶體佔用率  │    連線數     │   ← metric_cards(3 個 Metric)
 └──────────────┴──────────────┴──────────────┘
  若 exporter 未就緒（值為 None）→ 顯示 "N/A"
  每 1 秒自動刷新（@st.fragment(run_every=1.0)，僅局部 rerun）
```

| 分頁 | 主要元件 | 備註 |
|---|---|---|
| 日誌 | `filter_bar(key_prefix="admin_log")` + `st.dataframe` + cursor 分頁按鈕 | 欄位：時間(UTC)/等級/模組/訊息/Request ID |
| DB 狀態 | `@st.fragment(run_every=1.0)` 包裹 `metric_cards()` | 唯讀；三個伺服器狀態指標；None 顯示 "N/A"；每 1 秒輪詢 |

---

## 功能細節

### 日誌分頁

接後端 `GET /monitoring/logs`（cursor-based 分頁）；詳細契約與決策見
[server-log.md](../server-log.md)（日誌部分的單一真相）。

```python
fp_log = filter_bar(
    categories=["全部", "INFO", "WARNING", "ERROR"],
    key_prefix="admin_log",
    show_keyword=False,
)

# 篩選改變 → 重設游標與棧（避免舊 cursor 與新篩選混用）
filter_sig = (fp_log.category, fp_log.date_from, fp_log.date_to)
if st.session_state.get("admin_log_filter_sig") != filter_sig:
    st.session_state["admin_log_filter_sig"] = filter_sig
    st.session_state["admin_log_cursor"] = None
    st.session_state["admin_log_cursor_stack"] = []

# mock：seed_logs() 以 level / ts 範圍在前端過濾，next_cursor=None
# api：ApiDataSource(_get_api_client(), base).get_logs(level=..., since_ms=...,
#      until_ms=..., cursor=..., limit=100)；失敗 render_error → empty_state("無法載入日誌")

st.dataframe(log_entries_to_rows(log_page.items), hide_index=True)
# [← 上一頁]（棧空禁用）  [下一頁 →]（next_cursor=None 禁用）
```

- 日期範圍以 `date_range_to_ms()` 轉 `since_ms / until_ms`（epoch ms，UTC）。
- 時間以 UTC 顯示（`format_log_ts`），UI 加「時間為 UTC」標注。

### DB 狀態分頁

#### 1 秒輪詢（`@st.fragment(run_every=1.0)`）

DB 狀態每 1 秒自動刷新一次。採用與 `pages/realtime_monitor.py` 的 `live_panel`
相同的 **`@st.fragment(run_every=...)`** 模式（Streamlit 官方局部 rerun 機制）：

- fragment 每 1 秒**只重跑分頁內容**，不觸發整頁 rerun——日誌分頁的篩選 /
  分頁狀態不受影響。
- mock / api 分支放在 **fragment 內**：mock 模式重跑靜態種子（無副作用），
  api 模式每次輪詢重新呼叫 `GET /monitoring/infra`。
- API 失敗時 `render_error(exc)` 後 **early `return`（不可 `st.stop()`）**——
  `run_every` 會繼續排程，後端恢復後下一輪自動切回指標畫面
  （同 `live_panel` 的錯誤恢復模式）。
- **不使用 `st.cache_data`**：輪詢的目的就是每 1 秒取新值，快取會使刷新失效。

```python
DB_STATUS_REFRESH_SECONDS = 1.0


@st.fragment(run_every=DB_STATUS_REFRESH_SECONDS)
def db_status_panel() -> None:
    if settings.use_mock:
        db = seed_db_status()
        infra = {
            "cpu_percent":    db["cpu_percent"],
            "memory_percent": db["memory_percent"],
            "db_connections": db["connections"],
        }
    else:
        from lib.data_source import _get_api_client

        try:
            infra = fetch_infra_snapshot(_get_api_client(), settings.fastapi_base_url)
        except Exception as exc:
            render_error(exc)
            return   # early return；run_every 續跑，後端恢復後自動切回指標

    metric_cards([
        Metric("CPU 佔用率",   format_percent(infra["cpu_percent"])),
        Metric("記憶體佔用率", format_percent(infra["memory_percent"])),
        Metric(
            "連線數",
            infra["db_connections"] if infra["db_connections"] is not None else "N/A",
        ),
    ])


with db_tab:
    db_status_panel()
```

#### 後端 API 規格（單一真相）

```
GET /monitoring/infra
Authorization: Bearer {access_token}
```

**回應**（`InfraHistoryResponse`）：

```json
{
  "snapshots": [
    {
      "ts": 1753000000000,
      "cpu_percent": 45.2,
      "memory_percent": 62.8,
      "disk_percent": 34.1,
      "db_connections": 5,
      "db_buffer_pool_hit_rate": 98.7
    }
  ]
}
```

- `snapshots` 由舊到新排列，**取最後一筆**（`snapshots[-1]`）為最新快照。
- `snapshots` 可能為空（後端剛啟動、尚無採樣記錄）→ 全部指標顯示 "N/A"。
- `cpu_percent: float | None`：node-exporter 未啟動 / 無法連線時為 `None`。
- `db_connections: int | None`：mysqld-exporter 未啟動 / 無法連線時為 `None`。
- `memory_percent: float`：永遠有值（psutil 本機取得）。

---

## `lib/system_management.py` 純函式契約（單一真相）

所有函式**無 Streamlit 依賴**，可直接單元測試。

| 函式 | 簽章 | 契約 |
|---|---|---|
| `color_log_level` | `(level: str) -> str` | `"ERROR"` / `"WARNING"` / `"INFO"` → 對應色彩 token；未知等級回中性色。（保留備用） |
| `format_db_size` | `(size_bytes: int) -> str` | 位元組 → `"{:.1f} MB"` 字串；`0 → "0.0 MB"`。（保留備用） |
| `format_percent` | `(value: float \| None) -> str` | `45.2 → "45.2%"`；`None → "N/A"`。 |
| `format_log_ts` | `(ts_ms: int) -> str` | epoch ms → `"YYYY-MM-DD HH:MM:SS"` UTC 字串。 |
| `date_to_epoch_ms` | `(d: date) -> int` | date → UTC 當日 00:00 epoch ms。 |
| `date_range_to_ms` | `(d_from, d_to) -> tuple[int, int]` | → `(since_ms, until_ms)`；until = d_to 當日 23:59:59.999。 |
| `log_entries_to_rows` | `(entries: list) -> list[dict]` | `LogEntry` list → `{"時間","等級","模組","訊息","Request ID"}` rows；`request_id=None → "—"`。 |
| `seed_logs` | `() -> list[LogEntry]` | mock 靜態日誌（對齊後端 LogEntry schema）；決定性、不依賴時鐘。 |
| `seed_db_status` | `() -> dict` | 回傳 `{"cpu_percent": 45.2, "memory_percent": 62.8, "connections": 5}`；決定性。 |
| `parse_infra_snapshot` | `(snapshots: list[dict]) -> dict` | 從後端 `InfraHistoryResponse.snapshots` 取最新一筆，回傳 `{"cpu_percent": float \| None, "memory_percent": float \| None, "db_connections": int \| None}`；空 list 時全部為 `None`。 |
| `fetch_infra_snapshot` | `(client: ApiClient, base_url: str) -> dict` | 呼叫 `GET {base_url}/monitoring/infra`，回傳 `parse_infra_snapshot(data["snapshots"])`；API 失敗向上拋例外。 |

### `parse_infra_snapshot` 實作細節

```python
def parse_infra_snapshot(snapshots: list[dict]) -> dict:
    if not snapshots:
        return {"cpu_percent": None, "memory_percent": None, "db_connections": None}
    latest = snapshots[-1]
    return {
        "cpu_percent":    latest.get("cpu_percent"),      # float | None
        "memory_percent": latest.get("memory_percent"),   # float | None（後端保證有值，但防守）
        "db_connections": latest.get("db_connections"),   # int | None
    }
```

### `fetch_infra_snapshot` 實作細節

```python
def fetch_infra_snapshot(client: "ApiClient", base_url: str) -> dict:
    data = client.request("GET", f"{base_url}/monitoring/infra")
    return parse_infra_snapshot(data.get("snapshots", []))
```

> `ApiClient` 已在 `lib/data_source._get_api_client()` 以 `lru_cache` 建立（process 生命週期共用）。
> 頁面呼叫 `_get_api_client()` 取得共用 client，不自行建立 httpx.Client。

---

## Mock 模式行為（`use_mock=True`）

| 分頁 | Mock 資料來源 |
|---|---|
| 日誌 | `seed_logs()` 靜態假日誌（含 INFO/WARNING/ERROR） |
| DB 狀態 | `seed_db_status()` 靜態假指標（`cpu_percent=45.2`、`memory_percent=62.8`、`connections=5`） |

- 兩分頁皆唯讀，無寫入操作，無可變 session_state。
- mock 模式下**不需登入 BFF** 亦可完整呈現；可直接以 AppTest 驗證。

---

## 資料

- 透過後端 **monitoring API** 存取 logs / db-status；前端不直接連 DB。
- 兩分頁皆唯讀。

---

## 權限規則

- **頁面進入**：`grade >= AdminRole.SUPER_ADMIN`（≥100）才可見此頁（由 `build_pages` 動態不註冊）。
- **日誌 / DB 狀態分頁**：所有進入者皆可讀取，無寫入。
- **認證**：`Bearer {access_token}`，由 `ApiClient`（`get_token=auth.get_access_token`）自動帶入。

---

## session_state 契約

使用頁面前綴（見 [UI Helper §7](../ui.md#7-狀態命名規範)）:

| Key | 前綴 | 由誰管理 | 說明 |
|---|---|---|---|
| `admin_log_category` | `admin_log_` | `filter_bar()` | 日誌分頁等級篩選 |
| `admin_log_date_from` | `admin_log_` | `filter_bar()` | 日誌分頁起始日期 |
| `admin_log_date_to` | `admin_log_` | `filter_bar()` | 日誌分頁結束日期 |
| `admin_log_cursor` | `admin_log_` | 頁面 | 當前頁游標（`None` = 第一頁） |
| `admin_log_cursor_stack` | `admin_log_` | 頁面 | 上一頁游標棧（list） |
| `admin_log_filter_sig` | `admin_log_` | 頁面 | 篩選簽章；改變時重設 cursor 與棧 |
| `last_request_id` | — | `render_error` | 管理 API 失敗時附錯誤代碼 |

---

## 狀態與錯誤處理

頁內所有操作失敗的呈現一律依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威):

| 情境 | 處理方式 |
|---|---|
| grade≥100 進入 | 頁面正常渲染（兩分頁皆可用），不出現「僅限 Admin」錯誤 |
| `GET /monitoring/infra` 失敗（逾時 / 連線錯誤 / 5xx） | `render_error(exc)` → `st.error`（附 request_id）→ **early `return`**（fragment 續跑，1 秒後自動重試；不可 `st.stop()`） |
| `snapshots` 為空（後端尚無採樣） | `parse_infra_snapshot([])` 回傳全 `None` → 三個指標均顯示 "N/A"（不報錯） |
| `cpu_percent` / `db_connections` 為 `None` | `format_percent(None)` → `"N/A"`；不報錯，靜默顯示 |
| `GET /monitoring/logs` 失敗 | `render_error(exc)` + `empty_state("無法載入日誌")` |
| 無日誌資料（篩選後） | `empty_state("無符合條件的日誌")` 取代列表 |

---

## lib/ 依賴

| 模組 | 用途 |
|---|---|
| `lib/ui.py` | `filter_bar`、`metric_cards`、`empty_state` |
| `lib/system_management.py` | `format_percent`、`format_log_ts`、`date_range_to_ms`、`log_entries_to_rows`、`seed_logs`、`seed_db_status`、`parse_infra_snapshot`、`fetch_infra_snapshot` |
| `lib/models.py`（日誌） | `LogEntry`、`LogsPage` 資料契約 |
| `lib/api_client.py` | `ApiDataSource.get_logs()`（cursor 分頁；api 模式才用） |
| `lib/data_source.py` | `_get_api_client()`（共用 ApiClient；api 模式才引入） |
| `lib/config.py` | `get_settings()`（`use_mock` / `fastapi_base_url`） |
| `lib/errors.py` | `render_error`（api 模式失敗時呈現） |
| `lib/models.py` | `AdminRole` 常數（grade 數值比較） |

---

## 可測試性 / TDD

### 里程碑順序

1. **`lib/system_management.py` 純函式**（unit 7–11）
2. **`pages/system_management.py` API 模式**（AppTest 7–9）
3. **DB 狀態 1 秒輪詢 fragment 化**（AppTest 10；既有測試 5–9 為重構護欄）

> 依 CLAUDE.md：Red → Green → Refactor；一個測試一段實作。

---

### 純函式（`tests/unit/test_system_management.py`，新增測試 7–11）

#### 7. `format_percent` — 正常值與 None

```python
def test_format_percent_normal():
    assert format_percent(45.2) == "45.2%"

def test_format_percent_zero():
    assert format_percent(0.0) == "0.0%"

def test_format_percent_none():
    assert format_percent(None) == "N/A"
```

#### 8. `parse_infra_snapshot` — 完整快照

```python
def test_parse_infra_snapshot_full():
    snapshots = [{"cpu_percent": 45.2, "memory_percent": 62.8, "db_connections": 5}]
    result = parse_infra_snapshot(snapshots)
    assert result["cpu_percent"] == 45.2
    assert result["memory_percent"] == 62.8
    assert result["db_connections"] == 5
```

#### 9. `parse_infra_snapshot` — exporter 未就緒（None 欄位）

```python
def test_parse_infra_snapshot_with_none_fields():
    snapshots = [{"cpu_percent": None, "memory_percent": 62.8, "db_connections": None}]
    result = parse_infra_snapshot(snapshots)
    assert result["cpu_percent"] is None
    assert result["db_connections"] is None
    assert result["memory_percent"] == 62.8
```

#### 10. `parse_infra_snapshot` — 空 list（後端剛啟動）

```python
def test_parse_infra_snapshot_empty_list():
    result = parse_infra_snapshot([])
    assert result == {"cpu_percent": None, "memory_percent": None, "db_connections": None}
```

#### 11. `parse_infra_snapshot` — 多筆時取最新（最後一筆）

```python
def test_parse_infra_snapshot_takes_latest():
    snapshots = [
        {"cpu_percent": 10.0, "memory_percent": 20.0, "db_connections": 1},
        {"cpu_percent": 50.0, "memory_percent": 70.0, "db_connections": 9},  # ← 最新
    ]
    result = parse_infra_snapshot(snapshots)
    assert result["cpu_percent"] == 50.0
    assert result["db_connections"] == 9
```

---

### 頁面行為（`tests/app/test_system_management.py`，新增測試 7–9）

> **AppTest 測試策略（api 模式）**
>
> 直接測頁面檔（`PAGE_PATH`），不穿越 app.py auth dance——
> `require_auth()` 在 `use_mock=False` + `session_state["actor"]` 已設時自動通過（同 `test_realtime_monitor.py` 的 `_open_monitor_api` 模式）。
>
> `fetch_infra_snapshot` 以 `monkeypatch.setattr` 替換為回傳固定 dict 的 stub，
> 不需啟動真實後端。

```python
from pathlib import Path
from unittest.mock import patch

PAGE_PATH_DIRECT = str(Path(__file__).resolve().parents[2] / "pages" / "system_management.py")

def _open_system_management_api(actor, monkeypatch, mock_infra: dict) -> AppTest:
    """use_mock=False helper：直接測頁面、stub fetch_infra_snapshot。"""
    monkeypatch.setenv("USE_MOCK", "false")
    monkeypatch.setattr(
        "lib.system_management.fetch_infra_snapshot",
        lambda *_: mock_infra,
    )
    at = AppTest.from_file(PAGE_PATH_DIRECT)
    at.session_state["actor"] = actor
    at.run()
    return at
```

#### 7. 正常快照 → 三個指標含數值

```python
def test_db_tab_api_shows_metrics_with_values(monkeypatch):
    at = _open_system_management_api(
        Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN),
        monkeypatch,
        {"cpu_percent": 45.2, "memory_percent": 62.8, "db_connections": 5},
    )
    assert not at.exception
    metric_values = {m.label: m.value for m in at.metric}
    assert metric_values.get("CPU 佔用率") == "45.2%"
    assert metric_values.get("記憶體佔用率") == "62.8%"
    assert metric_values.get("連線數") == "5"
```

#### 8. exporter 未就緒（None）→ 顯示 "N/A"，不報錯

```python
def test_db_tab_api_shows_na_when_exporter_unavailable(monkeypatch):
    at = _open_system_management_api(
        Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN),
        monkeypatch,
        {"cpu_percent": None, "memory_percent": 62.8, "db_connections": None},
    )
    assert not at.exception
    metric_values = {m.label: m.value for m in at.metric}
    assert metric_values.get("CPU 佔用率") == "N/A"
    assert metric_values.get("記憶體佔用率") == "62.8%"
    assert metric_values.get("連線數") == "N/A"
```

#### 9. API 呼叫失敗 → `render_error` → `st.error` 出現

```python
def test_db_tab_api_error_shows_error(monkeypatch):
    from lib.api_client import ApiError

    monkeypatch.setenv("USE_MOCK", "false")
    monkeypatch.setattr(
        "lib.system_management.fetch_infra_snapshot",
        lambda *_: (_ for _ in ()).throw(ApiError("連線失敗", status=None)),
    )
    at = AppTest.from_file(PAGE_PATH_DIRECT)
    at.session_state["actor"] = Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN)
    at.run()
    assert not at.exception
    assert at.error   # render_error → st.error 出現
```

#### 10. DB 狀態為 fragment 且 `run_every=1.0`

> **AppTest 與 `run_every` 的限制**：AppTest 只執行一次 script，無法快轉時間
> 驗證「每 1 秒重跑」——時間排程屬 Streamlit 框架保證，不自行測試。
> 可測的行為是：(a) fragment **首跑**即渲染三個指標（既有測試 5–9 已覆蓋，
> 作為 fragment 化重構的護欄）；(b) `db_status_panel` 確實以
> `run_every=1.0` 註冊為 fragment（以模組屬性斷言）。

```python
def test_db_status_panel_is_fragment_with_5s_interval():
    """db_status_panel 以 @st.fragment(run_every=1.0) 包裹（間隔為規格值 1 秒）。

    頁面模組 import 即執行 Streamlit 呼叫，故以原始碼字串斷言。
    """
    src = Path(PAGE_PATH_DIRECT).read_text(encoding="utf-8")
    assert "DB_STATUS_REFRESH_SECONDS = 1.0" in src
    assert "@st.fragment(run_every=DB_STATUS_REFRESH_SECONDS)" in src
```

> 註：頁面模組 import 即執行 Streamlit 呼叫，故此測試以原始碼字串斷言
> 常數與裝飾器存在（輕量護欄，防止間隔被改動而未同步規格）。
> 若嫌字串斷言脆弱，可省略此測試，僅以測試 5–9 護欄 fragment 化重構。

---

## API Endpoints（後端 `/monitoring/...`）

| 操作 | 方法 & 路徑 | 認證 | 回應 |
|---|---|---|---|
| 伺服器狀態（歷史） | `GET /monitoring/infra` | Bearer VIEWER+ | `InfraHistoryResponse { snapshots: list[InfraSnapshot] }` |
| 日誌查詢 | `GET /monitoring/logs` | Bearer SUPER_ADMIN | `Page[LogEntry]` |

> **路徑前綴為 `/monitoring/`，不是 `/admin/`**（對應後端 `router.py` prefix）。

---

## 依賴 / 備註

- 管理員管理（建立／改名／升降權／封存／刪除）已移至主前端 CMS（Next.js），後端 `/admin/admins/...` API 由主前端直接呼叫，Streamlit 不參與。
- `InfraSnapshot` 中 `memory_percent` 後端保證有值（psutil 本機取得），但 `parse_infra_snapshot` 仍以 `.get()` 防守，避免後端 schema 異動時靜默崩潰。
- `_get_api_client()` 使用 `lru_cache`，process 生命週期只建立一次 httpx.Client 連線池，頁面不應自行建立新的 httpx.Client。
- **輪詢負載**：每個開啟此頁的 admin session 每 1 秒發一次 `GET /monitoring/infra`（後端為記憶體內 ring buffer 查詢，成本低）。fragment 只在使用者停留於此頁時排程；離開頁面即停止。若日後 admin 數量成長造成壓力，再考慮拉長間隔或改 WebSocket 推送。
