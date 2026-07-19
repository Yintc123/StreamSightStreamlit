# StreamSight (Streamlit)

StreamSight 的 Streamlit 前端應用。以 `st.navigation` + `st.Page` 組成 4 頁多頁面架構，依登入角色動態註冊頁面；**Streamlit 為純前端 / API Client，不直接連 DB**，所有資料存取透過 FastAPI（StreamSightBackend）REST API，即時監控走 FastAPI WebSocket。

## 需求

- Python 3.9+
- [uv](https://docs.astral.sh/uv/)（套件管理）

## 快速開始

```bash
# 安裝相依套件（自動建立 .venv）
uv sync

# 準備環境變數（預設 USE_MOCK=true，離線可跑、無需後端）
cp .env.example .env

# 啟動應用
uv run streamlit run app.py
```

啟動後於瀏覽器開啟 http://localhost:8501。

> 預設 `USE_MOCK=true`：使用記憶體假資料 + mock 認證，不需啟動 FastAPI / BFF 即可開發。
> 要接真後端時，設 `USE_MOCK=false` 並填妥 `BFF_BASE_URL` / `FASTAPI_BASE_URL`。
> 完整設定項見 [`docs/specs/config.md`](docs/specs/config.md) 與 `lib/config.py`。

## 架構與安全

> ## 🔒 最核心的設計原則:瀏覽器永遠拿不到 JWT
>
> 這是**整個架構設計的第一因**——底下幾乎每個決策,都是為了守住這一條而推導出來的。
>
> JWT(FastAPI 的 Bearer access token)**全程不進瀏覽器**。它只存在 **Streamlit Python server 的記憶體**(`st.session_state["access_token"]`,per-session、不落檔、不寫 log),使用者端只有一顆**加密的共享 session cookie** 與渲染後的 UI。

### 為什麼整個架構長這樣 —— 全都源於上面那條原則

| 設計決策 | 之所以如此,是因為要「瀏覽器拿不到 JWT」 |
|---|---|
| **Streamlit 是純 API Client、不直接連 DB** | 資料與憑證都關在後端邊界之後,前端表面積最小 |
| **唯一 BFF 是 Next.js 主前端;Streamlit 不是 BFF** | 解 cookie(`SESSION_SECRET`)、Redis、refresh 這些危險能力全集中在 BFF,遠離瀏覽器可及範圍 |
| **採 token 交換(Design B),而非「讓前端讀 sessionId + Redis」** | 只交出一顆**短命、可撤銷**的 access token,爆炸半徑限單一使用者;絕不把 JWT 或 session 真相暴露到瀏覽器 |
| **JWT 只存 server 記憶體,不落檔 / 不 log / 不渲染** | 這就是「瀏覽器拿不到」的具體守法;靠遮蔽紀律 + 測試覆蓋維持 |

### 流程(Design B,見 [ADR 0003](docs/decisions/0003-auth-via-bff-token-exchange.md))

1. 使用者在**主前端**登入 → 種下綁父網域的加密 session cookie。
2. 瀏覽器把該 cookie 一併送到 Streamlit server → Streamlit **原封轉發**給 BFF `GET /api/auth/session` 換取身分與**短命 JWT**(Streamlit 不持有 `SESSION_SECRET`、不碰 Redis)。
3. Streamlit server 以 **Bearer JWT** 直連 FastAPI 業務 API。

> **實作紅線**:JWT 屬伺服器端機密,**不得**以 `st.write` / URL / query params / 自訂元件渲染到前端——這會直接違反最核心的設計原則,必須有測試守住。詳見 [認證流程規格](docs/specs/auth-flow.md)。

## 頁面

| 頁面 | 檔案 | 說明 |
|---|---|---|
| 資料管理 | `pages/data_management.py` | Record CRUD 與 CSV / JSON 匯入（預設落地頁；`/data_management`，`/` 與 404 fallback） |
| 即時監控 | `pages/realtime_monitor.py` | 接 FastAPI WebSocket 即時讀值與圖表 |
| 資料分析 | `pages/analytics.py` | 統計分析（`/analytics`） |
| 系統管理 | `pages/system_management.py` | Admin-only，非 Admin **動態不註冊**此頁 |

登入委派 Next.js 主前端：未登入時 `app.py` 直接跳轉登入頁，Streamlit 本身沒有登入頁。

## 專案結構

```
StreamSightStreamlit/
├── app.py                  # 進入點：頁面設定 → CSS → 身分解析(gate) → 依 role 組頁 → 路由
├── pages/                  # 4 個頁面（薄排版，邏輯委派 lib/）
├── lib/                    # 可測試的純邏輯層
│   ├── config.py           #   APP_ENV 環境模型與設定項（pydantic-settings）
│   ├── auth.py             #   身分單一出口 resolve_actor（mock / BFF token 交換）
│   ├── api_client.py       #   HTTP 層：FastAPI 業務 API + BFF introspection（JWT / 逾時 / 重試）
│   ├── data_source.py      #   資料存取介面（Protocol）與工廠
│   ├── mock_data_source.py #   記憶體假資料（USE_MOCK=true）
│   ├── models.py           #   Actor / Record 型別與 can_edit 權限函式
│   ├── nav.py              #   依 role 動態組頁清單
│   ├── realtime.py         #   即時監控純函式
│   ├── realtime_ws.py      #   背景執行緒 WebSocket client
│   ├── analytics.py        #   資料分析純函式
│   ├── system_management.py#   系統管理純函式
│   ├── import_utils.py     #   CSV / JSON 匯入解析
│   ├── errors.py           #   例外 → (層級 / 文案 / request_id) 錯誤呈現
│   ├── request_id.py       #   X-Request-ID 跨服務關聯 + 結構化 logging
│   ├── state.py            #   session_state 讀寫 helper
│   └── theme.py / topbar.py / ui.py   # 主題、TopBar、共用 UI
├── styles/main.css         # 共用自訂 CSS（主題優先，CSS 最小化）
├── .streamlit/config.toml  # Streamlit 主題設定
├── tests/
│   ├── unit/               # lib/ 單元測試
│   └── app/                # streamlit.testing.v1.AppTest 頁面互動測試
├── docs/
│   ├── architecture.md     # 技術架構（方案 A / B，採 B）
│   ├── decisions/          # ADR（即時架構、API Client、BFF token 交換）
│   └── specs/              # 各模組與頁面規格
├── Dockerfile              # multi-stage（uv sync → python:3.13-slim runtime）
├── pyproject.toml          # 專案設定與相依套件
└── uv.lock                 # 鎖定套件版本
```

## 開發

本專案採**嚴格 TDD**（Red → Green → Refactor），詳見 [CLAUDE.md](CLAUDE.md)。

```bash
uv run pytest                 # 全部測試（提交前必跑）
uv run pytest tests/unit -v   # 只跑單元測試
uv run pytest tests/app -v    # 只跑頁面互動測試（AppTest）
uv run pytest -k <關鍵字> -x   # 篩選 + 首敗即停（TDD 迴圈常用）

uv add <package>              # 新增套件（不用 pip / brew）
```

慣例：

- 邏輯放 `lib/`（純函式、可單測），頁面只做排版與呼叫。
- 新增 `lib/` 邏輯 → 補 unit 測試；新增 / 修改頁面行為 → 補 AppTest 測試。
- 存取控制靠**動態不註冊**頁面（而非隱藏連結），且需測試覆蓋。

## Docker

```bash
docker build -t streamsight-streamlit .
docker run --rm -p 8501:8501 --env-file .env streamsight-streamlit
```

整合部署（與 Backend / Frontend / GoServer 一起）見 repo 根目錄的 `docker-compose.yml` 與 [根 README](../README.md)。

## 文件

- [技術架構](docs/architecture.md)
- ADR：[0001 即時架構](docs/decisions/0001-realtime-architecture.md)、[0002 Streamlit 純 API Client](docs/decisions/0002-streamlit-as-api-client.md)、[0003 BFF token 交換](docs/decisions/0003-auth-via-bff-token-exchange.md)
- 規格：[設定](docs/specs/config.md)、[認證流程](docs/specs/auth-flow.md)、[頁面結構](docs/specs/frontend-pages.md)、[設計系統](docs/specs/design-system.md)、[錯誤處理](docs/specs/error-handling.md)（其餘見 `docs/specs/`）
