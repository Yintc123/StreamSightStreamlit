# ADR 0001:即時監控採 Streamlit + FastAPI(WebSocket 推送)

- 狀態:已採用
- 日期:2026-07-18

## 背景

即時監控模組要求「WebSocket 連接推送即時資料」。Streamlit 的執行模型為每次互動整個 script 重跑,**不開放自寫 WebSocket handler**,無法由伺服器主動 push 到任意 client;原生只能以定時輪詢(`st.fragment(run_every)`、`streamlit-autorefresh`)模擬即時效果。

因此在兩方案間抉擇:

- **方案 A**:純 Streamlit,以定時輪詢模擬即時。架構單純,但非真正 WebSocket 推送。
- **方案 B**:Streamlit + FastAPI,由 FastAPI 負責即時資料生成與 WebSocket 推送,Streamlit 專注 UI/查詢/分析,共用同一 DB。

## 決策

採用**方案 B**。將 WebSocket 視為硬性技術需求,由 FastAPI 提供真正的伺服器推送。

## 理由

- 符合規格書對 WebSocket 推送的明確要求(方案 A 只是輪詢,不符合)。
- 即時資料生成器與告警判斷放在長駐的 FastAPI 服務,較符合「每秒生成 + 主動推送」的語意。
- Streamlit 與 FastAPI 職責分離,各自單純;共用同一 DB 便於資料一致。

## 影響

- **新增 FastAPI 服務**:即時資料生成器(每秒)、`/ws/live` WebSocket 端點、閾值告警。
- **資料庫**:採 Postgres(多人 + 兩服務共用),開發可先用 SQLite。
- **前端即時圖表**:需要能連 WebSocket 的前端元件在 Streamlit 中呈現即時更新。
- **部署複雜度上升**:需同時部署並協調 Streamlit 與 FastAPI 兩個服務。
- 資料管理、分析、系統管理模組(2/4/5)仍由 Streamlit 服務層負責,不受影響。

## 參考

- [技術架構](../architecture.md)
- [功能能力對照](../specs/feature-capability.md)
