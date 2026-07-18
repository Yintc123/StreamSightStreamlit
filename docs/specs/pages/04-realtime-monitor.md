# 頁面規格：即時監控（DB 資源使用狀況）

- 頁面編號：4
- 對應檔案：`pages/realtime_monitor.py`
- 存取權限：已登入 admin
- 資料來源：FastAPI `GET /admin/monitoring/infra`（見 [infra-monitoring.md](../../../../StreamSightBackend/docs/specs/infra-monitoring.md)）

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
│ CPU 使用率│ 記憶體   │ 磁碟使用率│ 連線數    │ Buffer Pool 命中 │ ← st.columns(5) + st.metric
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
| 即時指標列 | `st.columns(5)` + `st.metric` | 顯示最新一筆快照的各指標值 |
| CPU 折線圖 | `st.line_chart(df[["cpu_percent"]])` | 單線，x 軸為時間戳 |
| 記憶體/磁碟折線圖 | `st.line_chart(df[["memory_percent","disk_percent"]])` | 雙線同圖 |
| IOPS 折線圖 | `st.line_chart(df[["disk_read_iops","disk_write_iops"]])` | 雙線同圖 |
| 連線數折線圖 | `st.line_chart(df[["db_connections"]])` | 單線 |
| 最後更新時間 | `st.caption` | 顯示最新一筆 `ts` 轉換後的本地時間 |

---

## 功能細節

### 自動刷新

```python
time.sleep(5)
st.rerun()
```

每 5 秒重跑整個頁面，重新呼叫 API 並更新圖表。不使用第三方 auto-refresh 元件，無額外依賴。

### 資料取得

```python
data = api_client.request("GET", "/admin/monitoring/infra")
snapshots = data["snapshots"]  # list of InfraSnapshot，由新到舊
```

轉成 pandas DataFrame，index 為 `ts`（epoch ms 轉 datetime），欄位為各指標。資料為空時顯示 `st.info` 空狀態。

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

取最新一筆（`snapshots[0]`）的各欄位顯示於 `st.metric`：
- `cpu_percent` 為 `null` 時顯示 `—`
- `db_buffer_pool_hit_rate` < 95% 時以 `delta_color="inverse"` 標示

---

## 資料

- 唯讀頁面，不做寫入。
- 資料由 FastAPI `InfraSampler` background task 每 5 秒採集，存 Redis List，保留 60 筆（≈ 5 分鐘）。
- 前端不直接連 Redis 或 exporter，只透過 `ApiClient` 呼叫 FastAPI REST endpoint。

---

## 狀態與錯誤處理

依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威)：

| 情境 | 呈現 |
|---|---|
| API 呼叫失敗 / 逾時 | `ApiError` → `st.error` + 保留頁面框架 + 停止自動刷新 |
| FastAPI 回 503（Redis 不可用） | `st.error`「監控服務暫時無法使用」 |
| 資料為空（sampler 剛啟動） | `st.info`「資料採集中，請稍候…」取代圖表 |
| `cpu_percent = null`（第一筆） | 指標列顯示 `—`；折線圖自動跳過該點 |

---

## 依賴

- FastAPI `GET /admin/monitoring/infra` 需上線（見 [infra-monitoring.md](../../../../StreamSightBackend/docs/specs/infra-monitoring.md)）。
- `node-exporter`（`:9100`）與 `mysqld-exporter`（`:9104`）需在 infra compose 中運行。
- `prometheus-client` 套件需加入 FastAPI 的依賴（用於 Prometheus text format 解析）。
- Streamlit 端無新增依賴（pandas 已存在）。
