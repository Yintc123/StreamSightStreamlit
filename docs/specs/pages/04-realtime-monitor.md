# 頁面規格:即時監控

- 頁面編號:4
- 對應模組:模組 3 即時監控
- 存取權限:已登入使用者
- 架構:方案 B(Streamlit + FastAPI WebSocket),見 [ADR 0001](../../decisions/0001-realtime-architecture.md)

## 目的

即時呈現由 FastAPI 生成並推送的資料,更新圖表並在數值超過閾值時告警。

## 版面

以 `st.tabs` 分為兩個分頁:即時圖表 / 告警。

## UI 版面規劃

寬版,頂部連線狀態橫幅,`st.tabs(["即時圖表", "告警"])`。閾值控制放側邊欄。

```
● 已連線 /ws/live   最後更新 12:00:03                   ← 狀態橫幅(綠/紅)

[側邊欄]              [ 即時圖表 ] [ 告警 ]              ← st.tabs
 閾值設定             ── 即時圖表 ──────────────────────────
 上限 [====|==] 90    ┌─────────────────────┐┌──────────┐
 下限 [==|====] 10    │  折線圖(數值×時間)   ││ 柱狀圖    │  ← st.columns([2,1])
 [Admin]全域預設      │  滑動視窗最近 N 點    ││ 各分類    │     st.line_chart /
 [ 套用 ]            └─────────────────────┘└──────────┘     st.bar_chart

                     ── 告警 ──────────────────────────────
                     🔔 toast + 列表:時間 分類 數值 閾值 狀態
```

| 區域 | 元件 | 備註 |
|---|---|---|
| 連線狀態 | `st.status` / 帶色 `st.caption` | 綠=已連線,紅=重連中 |
| 即時圖表 | `st.columns([2,1])` + line/bar chart | 由 WebSocket 元件或 `fragment(run_every)` 更新 |
| 閾值控制 | `st.sidebar` + `st.slider`/`number_input` | 變更即時生效;Admin 才顯示全域預設 |
| 告警觸發 | `st.toast` + 圖上標記 + 列表 | 超閾值列以 warning/danger 色 |
| 斷線 | `st.warning` 重連中 | 自動重連 |

> 真正 WebSocket 由 FastAPI 提供(方案 B);Streamlit 端以可連 WS 的前端元件或定時刷新呈現,取捨見 [功能能力對照](../feature-capability.md)。

## 功能細節

### 即時圖表
- 透過 WebSocket 長連線(FastAPI `/ws/live`)接收每秒資料。
- 折線圖:數值隨時間變化。
- 柱狀圖:各分類即時分佈。
- 保留最近 N 點的滑動視窗,避免無限增長。

### 告警
- 閾值設定:上限 / 下限(可由使用者調整,Admin 可設全域預設)。
- 閾值變更透過 API 送後端;超閾值判斷與告警寫入由後端負責,前端顯示圖上標記 + `st.toast`/`st.warning`。
- 告警列表:時間、分類、數值、觸發閾值、狀態。

## 即時資料流

1. FastAPI 生成器每秒產生資料 → 寫入 DB。
2. 透過 `/ws/live` 主動推送(含告警判斷結果)。
3. 前端 WebSocket 元件收到後更新圖表 / 觸發告警。

> Streamlit 無原生伺服器推送;真正的 WebSocket 由 FastAPI 提供。前端需可連 WebSocket 的元件在 Streamlit 中呈現。

## 資料

- 即時資料與告警由**後端**擁有並落地(records / realtime、alerts 表);前端經 WebSocket 接收即時串流、經 REST API 讀取告警列表與變更閾值,不直接連 DB。
- alerts 表:`id, category, value, threshold, triggered_at, status`。

## 狀態與錯誤處理

- WebSocket 斷線 → 顯示重連中,嘗試自動重連。
- 無資料 → 空狀態提示。

## 依賴 / 備註

- 需要 FastAPI 服務同時運行(見技術架構方案 B)。
- 閾值變更需即時生效。
