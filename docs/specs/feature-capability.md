# 功能能力對照(Streamlit 可行性)

本文件盤點各模組功能在 **Streamlit** 上的可行性,並標示需要注意的技術取捨。

圖例:✅ 適合 / ⚠️ 可做但有取捨 / ❌ 非 Streamlit 原生能力

---

## 2. 資料管理模組 — 幾乎全部 ✅

| 項目 | 可行性 | 說明 |
|---|---|---|
| 建立資料(標題/數值/分類/時間戳) | ✅ | `st.form` + 寫入 DB(SQLite/Postgres) |
| 讀取(分頁、篩選、排序) | ✅ | `st.dataframe` 內建排序;分頁/篩選用 pandas 或 SQL query |
| 更新(限創建者/Admin) | ✅ | 權限判斷在 Python 端,`st.session_state` 存登入者角色 |
| 刪除(限創建者/Admin) | ✅ | 同上 |
| 批量匯入 CSV/JSON | ✅ | `st.file_uploader` + `pandas.read_csv/json` |

## 3. 即時監控模組 — 需注意 WebSocket 限制 ⚠️

| 項目 | 可行性 | 說明 |
|---|---|---|
| 模擬即時資料生成器(每秒) | ✅ | `@st.fragment(run_every="1s")` 定時重跑,不需背景 thread |
| WebSocket 連接推送 | ❌ / ⚠️ | Streamlit 不開放自寫 WebSocket handler,無法 server 主動 push 到任意 client。實務上以**輪詢/定時刷新**(`run_every`、`streamlit-autorefresh`)模擬即時,並非真正 push |
| 前端即時圖表更新(折線/柱狀) | ✅ | fragment 每秒重畫 `st.line_chart`/`st.bar_chart`/Plotly |
| 資料異常告警(超閾值標記) | ✅ | Python 判斷 + `st.warning`/顏色標記/`st.toast` |

> **關鍵取捨**:若「WebSocket」為硬性技術要求,Streamlit 不符合(它做的是定時輪詢)。若要求為「畫面每秒自動更新」的效果,則 Streamlit fragment 可達成。需與需求方確認。

## 4. 資料分析模組 — 全部 ✅

| 項目 | 可行性 | 說明 |
|---|---|---|
| 統計(總計/平均/最大/最小) | ✅ | pandas `describe()`/`agg()` |
| 時間範圍查詢 | ✅ | `st.date_input` + query |
| 分類聚合 | ✅ | `groupby` |
| 趨勢圖表 | ✅ | line chart / Plotly |
| 下載 Excel | ✅ | `st.download_button` + `openpyxl`(`BytesIO` 產生 .xlsx) |

## 5. 系統管理模組(Admin) — 全部 ✅

| 項目 | 可行性 | 說明 |
|---|---|---|
| 使用者列表 | ✅ | CRUD 讀取畫面,角色 gate |
| 權限管理 | ✅ | 更新 users 表 role 欄位 |
| 系統日誌查詢 | ✅ | logs 表查詢顯示 |
| 資料庫狀態監控 | ✅ | 查 DB 連線/表列數/大小顯示 |
| 即時資料歷史查詢 | ✅ | 即時資料落地 DB 後即為一般查詢 |

---

## 總結

- **可以做**:第 2、4、5 模組完整可做;第 3 模組的生成器、圖表更新、告警也可做。
- **唯一真正限制**:第 3 模組的 **WebSocket 推送**。Streamlit 無原生伺服器推送,僅能以定時輪詢/fragment 模擬即時效果。
- 若需真正 WebSocket,建議採 **FastAPI(WebSocket + 即時資料生成)+ Streamlit(UI/查詢/分析)** 共用同一 DB 的架構。

架構詳見 [技術架構](../architecture.md)。
