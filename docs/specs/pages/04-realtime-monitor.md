# 頁面規格:即時監控

- 頁面編號:4
- 對應模組:模組 3 即時監控
- 存取權限:已登入使用者
- 架構:方案 B(Streamlit + FastAPI WebSocket),見 [ADR 0001](../../decisions/0001-realtime-architecture.md)

## 目的

即時呈現由 FastAPI 生成並推送的資料,更新圖表並在數值超過閾值時告警。

## 版面

以 `st.tabs` 分為兩個分頁:即時圖表 / 告警。

## 功能細節

### 即時圖表
- 透過 WebSocket 長連線(FastAPI `/ws/live`)接收每秒資料。
- 折線圖:數值隨時間變化。
- 柱狀圖:各分類即時分佈。
- 保留最近 N 點的滑動視窗,避免無限增長。

### 告警
- 閾值設定:上限 / 下限(可由使用者調整,Admin 可設全域預設)。
- 超閾值時:圖上標記 + `st.toast`/`st.warning` + 寫入告警表。
- 告警列表:時間、分類、數值、觸發閾值、狀態。

## 即時資料流

1. FastAPI 生成器每秒產生資料 → 寫入 DB。
2. 透過 `/ws/live` 主動推送(含告警判斷結果)。
3. 前端 WebSocket 元件收到後更新圖表 / 觸發告警。

> Streamlit 無原生伺服器推送;真正的 WebSocket 由 FastAPI 提供。前端需可連 WebSocket 的元件在 Streamlit 中呈現。

## 資料

- 即時資料落地:records / realtime 表。
- alerts 表:`id, category, value, threshold, triggered_at, status`。

## 狀態與錯誤處理

- WebSocket 斷線 → 顯示重連中,嘗試自動重連。
- 無資料 → 空狀態提示。

## 依賴 / 備註

- 需要 FastAPI 服務同時運行(見技術架構方案 B)。
- 閾值變更需即時生效。
