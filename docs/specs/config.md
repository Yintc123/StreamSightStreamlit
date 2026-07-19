# 規格:設定模組(`lib/config.py`)

集中定義 Streamlit 前端的**執行環境模型**與**完整設定項清單**,對齊後端 [`StreamSightBackend/app/core/config`](../../StreamSightBackend/app/core/config) 與前端 BFF [`StreamSightFrontend/src/lib/config.ts`](../../StreamSightFrontend/src/lib/config.ts) 的慣例,避免三端各自發明一套。

- 前提:[ADR 0002](../decisions/0002-streamlit-as-api-client.md)(純 API Client,不連 DB)、[應用骨架 §2 旗標](app-skeleton.md#2-執行模式與旗標)。
- **安全邊界(硬性)**:Streamlit 是 client,**不持有任何 secret**——不放 JWT 簽章密鑰、DB / Redis 憑證、`SESSION_SECRET`、加密金鑰。這些屬後端 / BFF。本模組只保有「呼叫對外服務」所需的**非機密**設定(base URL、cookie 名、逾時、旗標)。

---

## 1. 環境模型(`APP_ENV`)——鏡像後端 `AppEnv`

單一環境選擇器 `APP_ENV`,值域與後端 [`app/core/enums.py::AppEnv`](../../StreamSightBackend/app/core/enums.py) **完全一致**:

| `APP_ENV` | 用途 | 對應後端 |
|---|---|---|
| `local` | 開發者本機;預設全 mock,不需 BFF / 後端 | `LocalAppSettings` |
| `development` | 共用 dev 環境,接 dev BFF / API | `DevAppSettings` |
| `stage` | 預備環境,接 stage BFF / API,近正式守衛 | (後端有 `STAGE` 列舉值) |
| `production` | 正式;強制 HTTPS、非 localhost、禁 mock | `ProdAppSettings` |
| `test` | pytest 專用;**hermetic,忽略 `.env`**,強制 mock | `TestAppSettings` |

- 小寫正規化:`APP_ENV` 讀入後一律 `.lower()`(同後端 `_normalize_app_env`);未知值 → **啟動即拋錯**,列出合法值(同後端 `get_app_settings`)。
- 預設 `local`(同後端)。
- **架構鏡像後端**:`BaseSettings`(所有欄位 + 驗證)+ 每環境子類覆寫預設 + `get_settings()` 依 `APP_ENV` 選類並 `lru_cache`(見 §6)。

> `APP_ENV` 設定「**該環境的預設值**」(如 base URL、旗標、log 等級);`USE_MOCK` 仍可用環境變數覆寫(§3)。

---

## 2. 與模式旗標的關係

[應用骨架 §2](app-skeleton.md#2-執行模式與旗標) 的兩個舊旗標（`DATA_SOURCE` / `AUTH_MODE`）**整合為單一布林旗標 `USE_MOCK`**,對齊前端 BFF 的慣例：

- **`USE_MOCK=true`（`1`）**:資料走 `MockDataSource`（記憶體）、身分走開發切換器；不需 BFF / FastAPI。
- **`USE_MOCK=false`（`0`）**:資料走 `ApiDataSource`（呼叫 FastAPI）、身分走 BFF introspection；需要真實後端。
- 兩模式互斥，無需守衛；`DATA_SOURCE=api + AUTH_MODE=mock` 的無效組合在語意上不再存在。

---

## 3. 完整設定項清單

env 變數名以大寫呈現;pydantic-settings **大小寫不敏感**對映到欄位(同後端 `case_sensitive=False`)。

### 3.1 App / meta

| env 變數 | 型別 | 預設 | 說明 / 對齊 |
|---|---|---|---|
| `APP_ENV` | enum | `local` | §1;對齊後端 `APP_ENV` |
| `APP_NAME` | str | `StreamSight` | 對齊前端 `NEXT_PUBLIC_APP_NAME` |
| `APP_VERSION` | str | `0.0.0` | 對齊前端 `APP_VERSION`;CI 覆寫 |
| `APP_COMMIT` | str? | `""` | 對齊前端 `APP_COMMIT` |
| `LOG_LEVEL` | enum | 依環境(§4) | `DEBUG/INFO/WARNING/ERROR/CRITICAL`,鏡像後端 `LogLevel`;大寫正規化 |

### 3.2 模式旗標(§2)

| env 變數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `USE_MOCK` | bool | 依環境(§4) | `true/1` → mock 全模式；`false/0` → api+bff 全模式；對齊前端 `USE_MOCK` |

### 3.3 BFF(Next.js)——introspection 目標

| env 變數 | 型別 | 預設(local) | 說明 |
|---|---|---|---|
| `BFF_BASE_URL` | url | `http://localhost:3000` | Next.js BFF base(前端跑 3000);**僅供 server-side 呼叫**(introspection / logout) |
| `BFF_PUBLIC_BASE_URL` | url | 空(回退 `BFF_BASE_URL`) | **瀏覽器可達**的 BFF base;登入重導 meta refresh 與 TopBar 連結用。docker compose 下 `BFF_BASE_URL` 是內部主機名(`http://frontend:3000`),此值必須設為對外位址(如 `http://localhost:3000`),否則重導會跳到瀏覽器打不開的頁面 |
| `BFF_SESSION_PATH` | str | `/api/auth/session` | introspection 端點(auth-flow §3) |
| `BFF_LOGOUT_PATH` | str | `/api/auth/logout` | 登出端點 |
| `BFF_LOGIN_PATH` | str | `/login` | Next.js 登入頁路徑;`actor is None` 時 meta refresh 跳轉目標 |
| `BFF_CMS_PATH` | str | `/cms` | CMS 根路徑;TopBar 品牌 & 管理後台連結目標（見 [topbar-cms-link.md](topbar-cms-link.md) §2.1） |
| `SESSION_COOKIE_NAME` | str | `streamsight_session` | **必須與前端 `SESSION_COOKIE_NAME` 一致**;`raw_cookie()` 據此讀 cookie 轉發 |
| `STREAMLIT_ORIGIN` | str | `http://localhost:8501` | Streamlit 本身的 origin;`_do_logout_bff()` 送 `Origin` header 時使用（015 §7.1B）；staging/prod 設 `https://dash.example.com`，需列入 BFF `ALLOWED_ORIGINS` |

### 3.4 FastAPI(後端)——業務 API 目標

| env 變數 | 型別 | 預設(local) | 說明 |
|---|---|---|---|
| `FASTAPI_BASE_URL` | url | `http://localhost:3001` | 後端 base(前端 `BACKEND_API_URL` 亦指 3001) |

### 3.5 HTTP client(api-client §2)

| env 變數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `HTTP_CONNECT_TIMEOUT_SECONDS` | float | `3` | 連線逾時 |
| `HTTP_READ_TIMEOUT_SECONDS` | float | `10` | 讀取逾時 |
| `HTTP_RETRY_MAX` | int | `2` | 網路重試上限(**僅 GET**) |
| `HTTP_RETRY_BASE_SECONDS` | float | `0.2` | 退避基值 |
| `HTTP_RETRY_FACTOR` | float | `2` | 退避倍率(→ 0.2 / 0.4;另加 ±50% 抖動) |

> **時間單位一律「秒」**,對齊後端慣例(後端 comment:「對時間參數的設置單位統一用秒」)。

### 3.6 Request ID(request-id §2)

| env 變數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `REQUEST_ID_HEADER` | str | `X-Request-ID` | header 名;待與 BFF/後端對齊(request-id §7) |
| `REQUEST_ID_PREFIX` | str | `st` | ID 前綴,標示源自 Streamlit |

### 3.7 認證 / token(auth-flow §4.6、§9)

| env 變數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `TOKEN_REFRESH_THRESHOLD_SECONDS` | int | `60` | `expiresAt - now <` 門檻 → 提前 refresh |
| `INTROSPECTION_CACHE_TTL_SECONDS` | int | `30` | introspection 快取 TTL(30–60) |
| `ROLE_ADMIN_VALUE` | int | `1` | role 數值 → `admin`,其餘 `user`;**待與前端 `Role` enum 對齊**(auth §7) |

### 3.8 閒置逾時([idle-timeout](idle-timeout.md) §7、§8)

| env 變數 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `IDLE_TIMEOUT_SECONDS` | int | `900` | 連續無滑鼠/鍵盤活動達此秒數 → 自動登出(15 分);純前端 JS 偵測 |
| `IDLE_ACTIVITY_THROTTLE_SECONDS` | int | `30` | 活動事件節流秒數,避免 `mousemove` 高頻洗版(偵測粒度 ±此值) |

---

## 4. 各環境預設矩陣

`APP_ENV` 選定後,以下為該環境**預設值**(仍可用個別 env 變數覆寫):

| 設定 | `local` | `development` | `stage` | `production` | `test` |
|---|---|---|---|---|---|
| `USE_MOCK` | `true` | `false` | `false` | `false` | `true` |
| `BFF_BASE_URL` | `localhost:3000` | dev BFF(待填) | stage BFF(待填) | prod BFF(待填) | 不使用 |
| `FASTAPI_BASE_URL` | `localhost:3001` | dev API(待填) | stage API(待填) | prod API(待填) | 不使用 |
| `LOG_LEVEL` | `DEBUG` | `DEBUG` | `INFO` | `INFO` | `WARNING` |
| 強制 HTTPS / 非 localhost | ✗ | ✗ | ✓ | ✓ | ✗ |
| 讀 `.env` | ✓ | ✓(部署變數) | ✓(部署變數) | ✓(部署變數) | **✗ hermetic** |

- `local` / `test` 全 mock,**不觸及 BFF / 後端**——對齊後端 `local`(debug)與 `test`(sqlite、忽略 .env)。
- dev/stage/prod 的實際 base URL **待部署架構確認**(§7);規格先留佔位。

---

## 5. 守衛 / 驗證(啟動即檢查)

鏡像後端 `field_validator` 與前端 `superRefine`:

1. **未知 `APP_ENV`** → 拋錯,列出合法值。
2. **`production` / `stage`**:`BFF_BASE_URL` 與 `FASTAPI_BASE_URL` 必須 **HTTPS 且非 `localhost`**(對齊前端「production requires non-localhost origins」、auth-flow §7.2 HTTPS-only)。
3. **`production` 禁 mock**:`USE_MOCK=true` 於 `production` → 拋錯(對齊前端「USE_MOCK must be '0' in production」)。
4. **`test` hermetic**:忽略 `.env`(`env_file=None`),只吃測試在 import 前設的環境變數(同後端 `TestAppSettings`)。
5. **空字串視為未設**:`KEY=` 當作未提供,套預設(對齊前端 `cleanedEnv`)。

---

## 6. 實作樣式(鏡像後端)

```python
# lib/config.py(概念,非最終碼)
from functools import lru_cache
from enum import Enum
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppEnv(str, Enum):
    LOCAL = "local"; DEVELOPMENT = "development"; STAGE = "stage"
    PRODUCTION = "production"; TEST = "test"

class BaseSettings_(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore", env_ignore_empty=True)
    app_env: AppEnv = AppEnv.LOCAL
    use_mock: bool = True   # true → mock data + mock auth；false → api + bff
    bff_base_url: str = "http://localhost:3000"
    fastapi_base_url: str = "http://localhost:3001"
    session_cookie_name: str = "streamsight_session"
    # … §3 其餘欄位 …
    # 守衛:§5 的 model_validator

class LocalSettings(BaseSettings_): pass                       # use_mock=True（繼承預設）
class DevSettings(BaseSettings_): use_mock: bool = False       # api + bff
class StageSettings(DevSettings): log_level = "INFO"           # + https 守衛
class ProdSettings(StageSettings): pass                        # 禁 mock 守衛
class TestSettings(BaseSettings_):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=False, extra="ignore")

_ENV_MAP = {AppEnv.LOCAL: LocalSettings, AppEnv.DEVELOPMENT: DevSettings,
            AppEnv.STAGE: StageSettings, AppEnv.PRODUCTION: ProdSettings, AppEnv.TEST: TestSettings}

@lru_cache
def get_settings() -> BaseSettings_:
    import os
    env = AppEnv(os.getenv("APP_ENV", "local").lower())   # 未知值 → ValueError
    return _ENV_MAP[env]()
```

- 對外只 export `get_settings()`;呼叫端不需知道分檔(同後端 `__all__`)。
- `pydantic-settings` 已列於 `pyproject.toml` 依賴(骨架必要模組;見 [app-skeleton §6](app-skeleton.md#6-lib-分層總表單一入口地圖))。

---

## 7. 相依 / 待確認

- [x] **環境模型**:採後端 `AppEnv` 5 值(`local/development/stage/production/test`),同名 `APP_ENV`、小寫、預設 `local`。
- [x] **安全邊界**:Streamlit config 不含任何 secret(JWT/DB/session 密鑰皆屬後端 / BFF)。
- [x] **cookie 名**:`streamsight_session`,對齊前端 `SESSION_COOKIE_NAME`。
- [x] **本機埠**:BFF `:3000`、FastAPI `:3001`(依前端 `.env` 與 `BACKEND_API_URL`)。
- [ ] **dev/stage/prod 實際 base URL**:待部署架構(同父網域前提,見 [auth-flow §9](auth-flow.md#9-未決--待確認))確認後填入 §4。
- [ ] **`ROLE_ADMIN_VALUE`**:對齊前端 / 後端 `Role` enum 整數值(承 [auth §7](auth.md))。
- [ ] **`REQUEST_ID_HEADER`**:與 BFF/FastAPI 對齊是否用 `X-Request-ID`(承 [request-id §7](request-id.md))。
- [x] **CSRF token 取得**:已定案（2026-07-18）。introspection 一併回傳 `csrfToken`，`_do_logout_bff()` 從 `state.get_csrf()` 取用；不需 `BFF_CSRF_PATH`（見 [015 §7.1A](../../StreamSightFrontend/docs/specs/015-streamlit-auth-bridge.md)）。

---

## 8. 可測試性 / TDD

放 `tests/unit/test_config.py`:

1. **環境選類** — `APP_ENV=local` → `LocalSettings`;`production` → `ProdSettings`;未知值 → `ValueError` 列出合法值。
2. **預設矩陣** — `local` 預設 `use_mock=True`;`development` 預設 `use_mock=False`(§4)。
3. **旗標覆寫** — `USE_MOCK=0` 可覆寫 local 預設。
4. **production 守衛** — `production` 下 localhost / `USE_MOCK=true` → 拋錯(§5.2–5.3)。
5. **test hermetic** — `APP_ENV=test` 時忽略 `.env`(不被本機 `.env` 汙染)。
6. **小寫 / 空字串正規化** — `APP_ENV=LOCAL` 可讀;`KEY=` 視為未設套預設。

> 骨架第一步(app-skeleton §10 步驟 1)即實作本模組的 `local` / `test` 路徑;dev/stage/prod 守衛可先寫測試,base URL 待確認後補。

---

## 9. 檔案與掛載

```
lib/config.py               # 本規格:AppEnv + BaseSettings 子類 + get_settings()
.streamlit/secrets.toml     # dev 本機設定(不入版控;app-skeleton §8)
.env / 部署環境變數          # 各環境注入(test 忽略)
tests/unit/test_config.py   # 測 1–7
pyproject.toml              # dependencies 含 pydantic-settings
```

> 於 [app-skeleton §6 lib 分層總表](app-skeleton.md#6-lib-分層總表單一入口地圖) 中 `lib/config.py` 詳規即本檔;為**骨架必要**模組(第一個被 TDD 的檔)。

---

## 10. 相關文件

- [應用骨架](app-skeleton.md)(旗標 §2、lib 分層 §6、落地順序 §10)
- [API Client](api-client.md)(逾時 / 重試參數、base URL 用途)
- [認證流程](auth-flow.md)(BFF 端點、cookie、token 門檻)
- [Request ID 模組](request-id.md)(header 名 / 前綴)
- 後端 [`app/core/config`](../../StreamSightBackend/app/core/config)、前端 [`src/lib/config.ts`](../../StreamSightFrontend/src/lib/config.ts)(對齊來源)
