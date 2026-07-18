# 前端頁面結構(Streamlit,6 頁)

Streamlit 前端切分為 6 個頁面,以 `st.navigation` + `st.Page` 組成,並依登入角色動態註冊。

## 頁面一覽

| # | 頁面 | 對應模組 | 存取權限 | 頁內分頁(tabs) | 規格 |
|---|---|---|---|---|---|
| 1 | 未登入導向頁(Auth Gate) | 模組 1 認證 | 未登入 | —(導向主前端登入) | [規格](pages/01-login.md) |
| 2 | 儀表板 / 首頁 | 總覽 | 已登入 | — | [規格](pages/02-dashboard.md) |
| 3 | 資料管理 | 模組 2 | 已登入(編輯/刪除限創建者或 Admin) | 列表 / 新增 / 匯入 | [規格](pages/03-data-management.md) |
| 4 | 即時監控 | 模組 3 | 已登入 | 即時圖表 / 告警 | [規格](pages/04-realtime-monitor.md) |
| 5 | 資料分析 | 模組 4 | 已登入 | 統計 / 趨勢 / 匯出 | [規格](pages/05-analytics.md) |
| 6 | 系統管理 | 模組 5 | **僅 Admin** | 使用者 / 權限 / 日誌 / DB 狀態 | [規格](pages/06-admin.md) |

## 存取控制

- 認證採 **Design B**(見 [ADR 0003](../decisions/0003-auth-via-bff-token-exchange.md)):auth gate 讀共享 cookie → 經主前端 BFF `GET /api/auth/session` 換取身分 / role 與短命 JWT,存於 `st.session_state`。
- 未登入時只註冊「未登入導向頁」,由該頁**導向主前端登入**(Streamlit 不自建登入 / 註冊表單)。
- 非 Admin 時**動態不註冊**「系統管理」頁面(比隱藏連結更安全)。
- 頁面內以 `st.tabs` 再分子功能。

## 檔案結構

```
app.py                        # 進入點:認證判斷 + st.navigation
pages/
├── dashboard.py              # 2. 儀表板
├── data_management.py        # 3. 資料管理
├── realtime_monitor.py       # 4. 即時監控(連 FastAPI WebSocket)
├── analytics.py              # 5. 資料分析
└── admin.py                  # 6. 系統管理(僅 Admin 註冊)
lib/
├── api_client.py             # FastAPI REST 呼叫封裝(帶 JWT、逾時 / 錯誤處理)
├── auth.py                   # 認證 / 角色 helper(呼叫後端取得 JWT,不碰 DB)
└── state.py                  # session_state helper(存 token / 角色)
```

> **資料存取原則**(見 [ADR 0002](../decisions/0002-streamlit-as-api-client.md)):所有頁面的資料存取一律透過 `lib/api_client.py` 呼叫 FastAPI,**Streamlit 不直接連 DB**。

## 相關文件

- [技術架構](../architecture.md)(方案 B:Streamlit + FastAPI)
- [設計系統 / 樣式規格](design-system.md)
- [功能能力對照](feature-capability.md)
- [資料來源抽象層(Mock 先行,之後換 API)](data-source.md)
- [ADR 0001:即時架構](../decisions/0001-realtime-architecture.md)
- [ADR 0002:Streamlit 為 API Client,不直接連 DB](../decisions/0002-streamlit-as-api-client.md)
