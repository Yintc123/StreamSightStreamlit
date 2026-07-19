# 前端頁面結構(Streamlit,4 頁)

Streamlit 前端切分為 4 個頁面,以 `st.navigation` + `st.Page` 組成,並依登入角色動態註冊。**登入委派 Next.js 主前端**:`app.py` 偵測未登入(無 cookie / introspection 401)時直接以 `<meta http-equiv="refresh">` 跳轉至 Next.js 登入頁(`BFF_BASE_URL + BFF_LOGIN_PATH`),無獨立 Streamlit 登入頁。

## 頁面一覽

| # | 頁面 | 對應模組 | 存取權限 | 頁內分頁(tabs) | 規格 |
|---|---|---|---|---|---|
| 1 | 資料管理 | 模組 2 | 已登入；寫入限 `grade > AdminRole.VIEWER`（>0） | 列表 / 新增 / 匯入 | [規格](pages/03-data-management.md) |
| 2 | 即時監控 | 模組 3 | 已登入 | —（單頁：即時圖表＋告警） | [規格](pages/04-realtime-monitor.md) |
| 3 | 資料分析 / 首頁 | 模組 4 | 已登入 | 統計 / 趨勢 / 匯出 | [規格](pages/05-analytics.md) |
| 4 | 系統管理 | 模組 5 | **僅 `grade >= AdminRole.SUPER_ADMIN`（≥100，含 ROOT=999）**（`editor` / `viewer` 不可見） | 日誌 / DB 狀態（管理員管理已移至主前端 CMS） | [規格](pages/06-admin.md) |

> **未登入導向**:由 `app.py` 直接處理(非頁面)。詳見 [Auth Gate 導向規格](pages/01-login.md)。
> **預設落地頁**:資料分析(`default=True`)。原「儀表板 / 首頁」已移除,登入後首先落在資料分析。

## 存取控制（本節為存取軸的單一真相）

- 認證採 **Design B**(見 [ADR 0003](../decisions/0003-auth-via-bff-token-exchange.md)):auth gate 讀共享 cookie → 經主前端 BFF `GET /api/auth/session` 換取身分 / `role` / `grade` 與短命 JWT,存於 `st.session_state`。
- 未登入時 `app.py` 直接 meta refresh 跳轉 Next.js 登入頁(**不註冊任何業務頁**)。此為**正常路徑守衛**；各業務頁面先頭另呼叫 `require_auth()`（`lib/auth.py`）作為**安全兜底層**，防禦 Streamlit MPA script runner 在 `app.py` 之後另行執行頁面時 session 已過期的邊緣情況（詳見 [Auth 模組 §3a](auth.md#3a-require_auth-頁面守衛安全兜底層)）。
- **本系統為 admin-only**:只有 `role == "admin"` 的身分能進入 StreamSight(由後端 / BFF 於發證時保證),故 `role` 在本前端**實質恆為 `"admin"`**;**真正的存取軸是 `grade`**——對應後端 `AdminRole` IntEnum 數值：`VIEWER=0` / `EDITOR=50` / `SUPER_ADMIN=100` / `ROOT=999`。
- **讀取**：資料管理 / 即時監控 / 資料分析三頁對所有 grade 開放；**系統管理頁僅 `grade >= AdminRole.SUPER_ADMIN`（≥100，含 ROOT=999）可見**，`editor`（50）與 `viewer`（0）不可見（動態不註冊，比隱藏連結更安全）。
- **寫入**:一律限 **`grade > AdminRole.VIEWER`**（`grade > 0`；`super_admin`/`root`/`editor` 可寫,`viewer` 唯讀）;判斷用純函式 **`can_write(actor)`**(單一真相)。資料管理的 CRUD **共用此條**;`viewer`（grade=0）一律以按鈕停用呈現,後端再強制驗證(深度防禦)。
- **頁面註冊**:`build_pages(actor)` 依 `actor.grade` 動態組頁；系統管理頁只在 `actor.grade >= AdminRole.SUPER_ADMIN` 時追加（非 Admin role 的 latent 防線仍保留，但主判斷已是 grade gate）。見[應用骨架 §5](app-skeleton.md#5-導覽與頁面註冊build_pages)。
- 頁面內以 `st.tabs` 再分子功能。

## 檔案結構

```
app.py                        # 進入點:認證判斷 + meta refresh(未登入)+ st.navigation
pages/
├── data_management.py        # 1. 資料管理
├── realtime_monitor.py       # 2. 即時監控(連 FastAPI WebSocket)
├── analytics.py              # 3. 資料分析(預設落地頁 default=True)
└── system_management.py      # 4. 系統管理(admin-only 系統,grade≥100 才註冊;寫入限 grade>0)
lib/                          # 本清單僅摘要;完整權威地圖見 app-skeleton §6
├── api_client.py             # FastAPI REST 呼叫封裝(帶 JWT、逾時 / 錯誤處理)
├── auth.py                   # 認證 / 角色 helper(呼叫後端取得 JWT,不碰 DB)
├── state.py                  # session_state helper(存 token / 角色)
├── errors.py                 # 例外 → st.error/warning/info 統一呈現
└── ui.py                     # 跨頁共用 UI Helper(篩選列、指標卡、分頁、空狀態)
```

> `lib/` 完整分層(`config`/`theme`/`nav`/`models`/`data_source`/`mock_data_source`/`request_id`/`errors` 等)以 [應用骨架 §6](app-skeleton.md#6-lib-分層總表單一入口地圖) 為單一真相,本頁不重列。

> **資料存取原則**(見 [ADR 0002](../decisions/0002-streamlit-as-api-client.md)):所有頁面的資料存取一律透過 `lib/api_client.py` 呼叫 FastAPI,**Streamlit 不直接連 DB**。

## 相關文件

- [技術架構](../architecture.md)(方案 B:Streamlit + FastAPI)
- [應用骨架 / 基礎架構(Walking Skeleton)](app-skeleton.md)
- [Auth 模組(`lib/auth.py` 契約)](auth.md)
- [設計系統 / 樣式規格](design-system.md)
- [功能能力對照](feature-capability.md)
- [資料來源抽象層(Mock 先行,之後換 API)](data-source.md)
- [ADR 0001:即時架構](../decisions/0001-realtime-architecture.md)
- [ADR 0002:Streamlit 為 API Client,不直接連 DB](../decisions/0002-streamlit-as-api-client.md)
