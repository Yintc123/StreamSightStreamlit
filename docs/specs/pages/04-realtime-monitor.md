# 頁面規格：即時監控（DB 資源使用狀況）

- 頁面編號：4
- 對應檔案：`pages/realtime_monitor.py`
- 存取權限：**已登入 Admin**（後端 `/admin/monitoring/infra` 需 Admin 角色；前端需在頁面進入時額外 gate）
- 資料來源：FastAPI `GET /admin/monitoring/infra`（見 [infra-monitoring.md](../../../../StreamSightBackend/docs/specs/infra-monitoring.md)）
- 相關：[UI Helper 規格](../ui.md)、[錯誤處理規格](../error-handling.md)、[應用骨架 §5](../app-skeleton.md#5-導覽與頁面註冊build_pages)

> **存取控制說明**：`build_pages` 目前把即時監控列入所有登入使用者的頁清單（[app-skeleton §5](../app-skeleton.md)），但 `/admin/monitoring/infra` 是後端的 Admin 端點，非 Admin 呼叫會得 403。**最佳實踐：** 應在 `build_pages` 中將此頁改為 Admin 才註冊，或在頁面頂端加 Admin gate（`if actor.role != "admin": st.error(...); st.stop()`）。暫定做法：於頁面頂端加 gate，`build_pages` 在後續 sprint 調整。

---

## 目的

即時呈現 DB 主機的硬體資源使用狀況（CPU / 記憶體 / 磁碟 / IOPS / 連線數），以折線圖顯示最近 5 分鐘的歷史趨勢，每 5 秒自動刷新。

---

## UI 版面規劃

寬版，由上而下：即時指標列 → 折線圖群。

```
┌──────────────────────────────────────────────────────────────┐
│ DB 即時監控                        最後更新 12:00:03          │ ← st.title + 右側 caption
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│ CPU 使用率│ 記憶體   │ 磁碟使用率│ 連線數    │ Buffer Pool 命中 │ ← metric_cards(5 個 Metric)
│  23.4 %  │  61.2 % │  45.8 % │   5      │  98.7 %         │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│ CPU 使用率（近 5 分鐘）                                        │ ← st.line_chart
│ ▁▂▃▄▃▂▁▂▃▄▅▄▃▂▃▄                                            │
├──────────────────────────────────────────────────────────────┤
│ 記憶體 / 磁碟使用率（近 5 分鐘）                               │ ← st.line_chart（雙線）
│ ▃▃▄▄▃▃▄▄▄▃▃▄▄▄▄▄  ← 記憶體                                  │
│ ▅▅▅▅▅▅▅▅▅▅▅▅▅▅▅▅  ← 磁碟                                    │
├──────────────────────────────────────────────────────────────┤
│ 磁碟 IOPS / 連線數（近 5 分鐘）                                │ ← st.columns(2) + st.line_chart
│ ┌──────────────────┐  ┌───────────────────┐                 │
│ │ 讀寫 IOPS（雙線） │  │ DB 連線數          │                 │
│ └──────────────────┘  └───────────────────┘                 │
└──────────────────────────────────────────────────────────────┘
```

| 區域 | 元件 | 備註 |
|---|---|---|
| 即時指標列 | `metric_cards(metrics)` | 5 個 `Metric`；`cpu_percent=null` 顯示 `"—"` |
| CPU 折線圖 | `st.line_chart(df[["cpu_percent"]])` | 單線，x 軸為時間戳 |
| 記憶體/磁碟折線圖 | `st.line_chart(df[["memory_percent","disk_percent"]])` | 雙線同圖 |
| IOPS 折線圖 | `st.line_chart(df[["disk_read_iops","disk_write_iops"]])` | 雙線同圖 |
| 連線數折線圖 | `st.line_chart(df[["db_connections"]])` | 單線 |
| 最後更新時間 | `st.caption` | 顯示最新一筆 `ts` 轉換後的本地時間 |

---

## 功能細節

### Admin Gate

```python
from lib.state import get_actor
actor = get_actor()
if actor is None or actor.role != "admin":
    st.error("此頁面僅限 Admin 存取")
    st.stop()
```

### 自動刷新

```python
time.sleep(5)
st.rerun()
```

每 5 秒重跑整個頁面，重新呼叫 API 並更新圖表。不使用第三方 auto-refresh 元件，無額外依賴。API 失敗時**停止刷新**（不繼續 `st.rerun()`）。

### 資料取得

```python
data = api_client.request("GET", "/admin/monitoring/infra")
snapshots = data["snapshots"]  # list of InfraSnapshot，由新到舊
```

轉成 pandas DataFrame，index 為 `ts`（epoch ms 轉 datetime），欄位為各指標。資料為空時顯示 `empty_state("資料採集中，請稍候…")`。

### 折線圖

```python
import pandas as pd

df = pd.DataFrame(snapshots)
df["ts"] = pd.to_datetime(df["ts"], unit="ms")
df = df.set_index("ts").sort_index()  # 由舊到新，折線圖由左到右

st.line_chart(df[["cpu_percent"]])
st.line_chart(df[["memory_percent", "disk_percent"]])
# ...
```

- 最多 60 筆（5 分鐘）
- 欄位含 `null` 時（如第一筆 CPU）pandas 自動跳過，折線不斷

### 即時指標列

取最新一筆（`snapshots[0]`），以 `metric_cards()` 渲染 5 個 `Metric`（見 [UI Helper §4](../ui.md#4-metric_cards--指標卡列)）：

```python
from lib.ui import metric_cards, Metric, empty_state

latest = snapshots[0] if snapshots else {}
metric_cards([
    Metric("CPU 使用率", f"{latest.get('cpu_percent', '—')} %" if latest.get('cpu_percent') is not None else "—"),
    Metric("記憶體", f"{latest.get('memory_percent', '—')} %"),
    Metric("磁碟使用率", f"{latest.get('disk_percent', '—')} %"),
    Metric("連線數", latest.get("db_connections", "—")),
    Metric("Buffer Pool 命中",
           f"{latest.get('db_buffer_pool_hit_rate', '—')} %",
           delta_color="inverse" if (latest.get("db_buffer_pool_hit_rate") or 100) < 95 else "off"),
])
```

- `cpu_percent` 為 `null` 時顯示 `"—"`
- `db_buffer_pool_hit_rate` < 95% 時 `delta_color="inverse"` 標示

---

## Mock 模式行為(`DATA_SOURCE=mock`)

即時監控依賴後端基礎設施端點，**在 mock 模式下無法取得真實資料**。行為如下：

```python
from lib.config import get_settings
settings = get_settings()

if settings.data_source == "mock":
    st.info("即時監控在 mock 模式下不可用。請切換至 DATA_SOURCE=api 並連線後端。")
    st.stop()
```

- **不做自動刷新**（避免空頁面無限 rerun）。
- 開發時若需測試 UI，可注入靜態假 snapshots 於測試或 `DATA_SOURCE=mock` 時走假資料分支（見 TDD 區段）。

---

## 資料

- 唯讀頁面，不做寫入。
- 資料由 FastAPI `InfraSampler` background task 每 5 秒採集，存 Redis List，保留 60 筆（≈ 5 分鐘）。
- 前端不直接連 Redis 或 exporter，只透過 `ApiClient` 呼叫 FastAPI REST endpoint。

---

## session_state 契約

使用 `rt_` 前綴（見[應用骨架 §7](../app-skeleton.md#7-session_state-契約單一真相)）：

| Key | 型別 | 說明 |
|---|---|---|
| `rt_last_error` | `Optional[str]` | 最近一次 API 失敗時記錄，用於決定是否停止自動刷新 |

- **不存歷史 snapshots 於 session_state**（每次 rerun 重取）——減少記憶體用量。

---

## 狀態與錯誤處理

依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威)：

| 情境 | 呈現 |
|---|---|
| 非 Admin 進入 | `st.error`「此頁面僅限 Admin 存取」+ `st.stop()` |
| API 呼叫失敗 / 逾時 | `ApiError` → `st.error` + 保留頁面框架 + **停止自動刷新** |
| FastAPI 回 503（Redis 不可用） | `st.error`「監控服務暫時無法使用」 |
| 資料為空（sampler 剛啟動） | `empty_state("資料採集中，請稍候…")` 取代圖表 |
| `cpu_percent = null`（第一筆） | 指標列顯示 `"—"`；折線圖自動跳過該點 |
| mock 模式 | `st.info`「mock 模式下不可用」+ `st.stop()` |

---

## lib/ 依賴

| 模組 | 用途 |
|---|---|
| `lib/ui.py` | `metric_cards`、`empty_state` |
| `lib/errors.py` | `render_error` |
| `lib/state.py` | `get_actor()`（Admin gate）|
| `lib/api_client.py` | `GET /admin/monitoring/infra` |
| `lib/config.py` | 判斷 `data_source` 決定 mock 模式行為 |

---

## 可測試性 / TDD

> **關鍵限制**：`time.sleep(5)` + `st.rerun()` 的自動刷新循環**無法直接以 AppTest 測試**（會導致測試無限循環）。測試策略：將資料轉換邏輯抽成純函式、以注入靜態 snapshots 測試 UI 行為，不測自動刷新本身。

### 純函式（`tests/unit/test_realtime_monitor.py`）

1. `snapshots_to_df(snapshots)` — 輸入假 snapshots 列表，輸出 DataFrame 已設 `ts` index、由舊到新排序。
2. `latest_metrics(snapshots)` — 輸入 snapshots，回傳 `List[Metric]`；`cpu_percent=None` 時對應 Metric.value 為 `"—"`。
3. `latest_metrics([])` — 回空 list（無資料時不拋例外）。
4. `db_buffer_pool_hit_rate < 95` → 對應 `Metric.delta_color == "inverse"`。
5. `db_buffer_pool_hit_rate >= 95` → `delta_color == "off"`。

### 頁面行為（`tests/app/test_realtime_monitor.py`，AppTest）

6. 非 Admin（`role="user"`）進入 → 頁面含「僅限 Admin」錯誤訊息。
7. mock 模式（`DATA_SOURCE=mock`）進入 → 頁面含 `st.info`「mock 模式下不可用」。
8. Admin + `DATA_SOURCE=api` + API 回假 snapshots → 含 5 個 `st.metric` 元件。
9. API 失敗（注入 `ApiError`）→ 頁面含 `st.error` 且含「錯誤代碼」。

> 依 CLAUDE.md，逐一先寫失敗測試 → 最小實作 → 綠燈重構。

---

## 依賴

- FastAPI `GET /admin/monitoring/infra` 需上線（見 [infra-monitoring.md](../../../../StreamSightBackend/docs/specs/infra-monitoring.md)）。
- `node-exporter`（`:9100`）與 `mysqld-exporter`（`:9104`）需在 infra compose 中運行。
- Streamlit 端無新增依賴（pandas 已存在）。
