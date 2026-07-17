# ADR 0002:Streamlit 一律透過 FastAPI 存取資料(不直接連 DB)

- 狀態:已採用
- 日期:2026-07-18
- 關聯:延伸並修正 [ADR 0001](0001-realtime-architecture.md)

## 背景

ADR 0001 採方案 B(Streamlit + FastAPI),但當時的分工是**兩服務共用同一 DB**:即時監控走 FastAPI WebSocket,其餘模組(資料管理、分析、系統管理、認證)由 **Streamlit 服務層直接讀寫 DB**。

實務上 monorepo 已有功能完整的 **StreamSightBackend**(FastAPI,含 JWT/Argon2 認證、users、repositories、services),且該後端本就是為了服務 Streamlit 前端而存在。若 Streamlit 仍自帶一套 DB 存取邏輯,會造成:

- 資料存取邏輯與權限規則**兩邊各寫一份**,易不一致。
- DB 連線與 schema 綁在前端,難以獨立部署與演進。
- 認證要在前端另接 `streamlit-authenticator`,與後端 JWT 體系重複。

## 決策

**Streamlit 定位為純前端 / API Client(BFF 模式),不直接連資料庫。** 所有資料存取——**認證、CRUD、查詢、分析、系統管理**——一律透過 HTTP 呼叫 **StreamSightBackend 的 REST API**;即時資料維持 FastAPI WebSocket 推送。**FastAPI 是唯一存取 DB 的服務。**

## 理由

- 資料存取與商業邏輯**單一來源**(後端),前端不重複實作、權限一致。
- 認證統一走後端 JWT(Argon2 雜湊),Streamlit 只保管 token,不自行雜湊或查 users 表。
- 前後端解耦:DB schema / 連線只在後端,前端可獨立改版與部署。
- 與既有 StreamSightBackend 直接對接,不必為前端另建資料層。

## 影響

- **前端新增 API Client 層**:`lib/api_client.py` 封裝 REST 呼叫,統一帶 `Authorization: Bearer <JWT>`、處理逾時 / 重試 / 錯誤轉譯。
- **認證改走 API**:登入 / 註冊呼叫後端 auth 端點取得 JWT,存於 `st.session_state`;角色由 token / `/me` 取得。**前端不再用 `streamlit-authenticator`,也不自行雜湊密碼**。
- **移除前端 DB 存取**:Streamlit 端不持有 DB 連線、不寫 SQL;分頁 / 篩選 / 聚合改用 API 查詢參數。
- **匯入 / 匯出**:CSV/JSON 匯入把解析後資料送 API 批量建立;Excel 匯出可由前端以 API 取回的資料產生,或呼叫後端匯出端點(擇一,見各頁規格)。
- **即時監控不變**:仍由 FastAPI 生成 + `/ws/live` 推送。
- **測試**:前端測試以 mock API Client(不打真實後端、不連 DB);`lib/` 邏輯與 API client 皆可單元測試。

## 參考

- [技術架構](../architecture.md)
- [ADR 0001:即時架構](0001-realtime-architecture.md)
- [前端頁面結構](../specs/frontend-pages.md)
