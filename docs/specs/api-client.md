# 規格:API Client(最小契約)

`lib/api_client.py` 是 Streamlit 唯一的對外 HTTP 層:封裝 **BFF introspection** 與 **FastAPI 業務 API** 呼叫,統一處理 JWT、逾時、重試、`X-Request-ID`、log 與錯誤轉譯,並提供 `ApiDataSource`(實作 `DataSource` 介面)。

- 前提:[ADR 0002](../decisions/0002-streamlit-as-api-client.md)(純 API Client,不連 DB)。
- 相關契約:[資料來源](data-source.md)(`DataSource` 介面、`Record` 型別、`RecordNotFound`/`PermissionDenied`/`ValidationError`)、[認證流程](auth-flow.md)(Bearer / reactive refresh)、[Request ID 模組](request-id.md)(`X-Request-ID`、`ApiError.request_id`)、[應用骨架](app-skeleton.md)(`get_data_source()`、`session_state`)。
- **範圍**:本規格只定「最小可實作契約」——錯誤模型、HTTP 選型、逾時/重試、呼叫流程、端點對應。進階(連線池調校、快取細節、匯出端點)不在此。

---

## 1. 職責與分層

| 角色 | 內容 | 觸發模式 |
|---|---|---|
| **introspection** | `GET {BFF}/api/auth/session` 換身分 + 短命 JWT(見 auth-flow §4) | `AUTH_MODE=bff` |
| **ApiDataSource** | 實作 [`DataSource`](data-source.md#介面定義datasource) 的 CRUD/匯入,呼叫 FastAPI 業務 API | `DATA_SOURCE=api` |

- 兩者共用同一套底層送出流程(§4):附 `X-Request-ID`、逾時、log、錯誤轉譯。
- `get_data_source()`(骨架 §6)在 `DATA_SOURCE=api` 時回傳 `ApiDataSource`。
- **不做**:登入表單、Set-Cookie、密碼雜湊(皆委派主前端 / 後端)。

> **旗標交互(硬性)**:`DATA_SOURCE=api` **必須搭** `AUTH_MODE=bff`——業務 API 需 Bearer JWT,而 JWT 只在 `bff` 模式下經 introspection 取得。`api` + `mock` 為無效組合,`get_data_source()` 應在啟動時**明確拋錯**(而非讓每次呼叫都 401)。允許的組合:`mock`+`mock`(dev)、`api`+`bff`(正式);`mock`+`bff` 亦可(真身分、假資料)。

---

## 2. HTTP client 選型與設定

| 項目 | 選擇 | 理由 |
|---|---|---|
| 函式庫 | **`httpx`**(同步 `httpx.Client`) | 型別友善、逾時/重試/transport mock 完整;與 [architecture.md](../architecture.md) 建議一致 |
| Client 生命週期 | 單一共享 `Client`(連線池),經 `lib/config.py` 建立 | 避免每次呼叫重建連線 |
| Base URL | `BFF_BASE_URL`、`FASTAPI_BASE_URL`(config) | introspection / 業務各自 base |
| 逾時 | `connect=3s`、`read=10s`(config 可調) | 明確逾時,避免 rerun 卡死 |
| 重試 / 退避 | GET 最多 2 次;base `0.2s`、factor `2`、±50% 抖動;sleep 可注入(config) | 見 §5;可注入 sleep 讓測試不等待 |
| TLS | 一律 HTTPS(正式) | token 只走加密通道(auth-flow §7) |

> 測試以 `httpx` 的 `MockTransport`(或 `respx`)注入假回應,**不打真後端**。

---

## 3. 錯誤模型

### 3.1 `ApiError`(傳輸層)

```python
# lib/api_client.py(概念)
class ApiError(Exception):
    def __init__(self, message, *, status=None, request_id=None, code=None):
        self.message = message
        self.status = status          # HTTP 狀態;逾時/連線錯誤為 None
        self.request_id = request_id  # 對應送出的 X-Request-ID(見 request-id §4.3)
        self.code = code              # 後端錯誤封包的 code(可選)
```

- 逾時、連線錯誤、5xx、非預期狀態 → 一律 `ApiError`(`status` 可能為 `None`)。
- **一定帶 `request_id`**,供頁面顯示與三端 log 對照(request-id §4.3)。

### 3.2 HTTP 狀態 → 例外映射

| 狀態 | 例外 | 來源 |
|---|---|---|
| 2xx | 正常回傳 | — |
| 400 / 422 | `ValidationError` | [models](data-source.md#例外) |
| 401 | 先 **reactive refresh** 重試一次(§5);仍 401 → `NotAuthenticated` → 導向登入 | auth-flow §4.3 |
| 403 | `PermissionDenied` | models |
| 404 | `RecordNotFound` | models |
| 408 / 429 / 5xx / 逾時 / 連線錯誤 | `ApiError` | 本規格 |
| 其他非預期 | `ApiError` | 本規格 |

- `NotAuthenticated` 為 `lib/`(auth 或 models)自訂例外;`app.py` 攔到即清狀態並導向主前端登入(auth-flow §4.4)。
- 域例外(`RecordNotFound`/`PermissionDenied`/`ValidationError`)沿用 `models.py`,**與 `MockDataSource` 同契約**——頁面錯誤處理 mock/api 一致(見 [03 頁面](pages/03-data-management.md#狀態與錯誤處理))。
- **本表(狀態→例外映射)為權威**;例外**如何呈現給使用者**(層級 / 文案 / 是否附 `request_id`)的權威在 [錯誤處理規格 §3](error-handling.md#3-呈現契約本規格唯一權威),頁面一律引用該表,不自訂。

### 3.3 後端錯誤封包

- 假設後端 / BFF 回**標準錯誤封包**(如 `{"error": {"code": "...", "message": "..."}}`);解析出 `message`/`code` 填入例外。
- 封包格式未定時,退回以 HTTP 狀態 + 原文訊息建立例外;實際格式**待與後端對齊**(§8)。

---

## 4. 單次呼叫流程(共用)

所有對外呼叫(introspection 與業務)走同一骨幹,差別只在**認證方式**:

```python
# 概念,非最終碼
def _request(method, url, *, headers=None, auth="bearer", json=None, **kw):
    rid = new_request_id(); set_current(rid)                 # request-id §4.1
    h = with_request_id(headers or {}, rid)
    if json is not None:
        h["Content-Type"] = "application/json"
    if auth == "bearer":                                     # 業務 API:帶 JWT
        h["Authorization"] = f"Bearer {auth_lib.get_access_token()}"
    elif auth == "cookie":                                   # introspection:轉發加密 cookie
        kw["cookies"] = {COOKIE_NAME: auth_lib.raw_cookie()} # 來自 st.context.cookies
    try:
        resp = client.request(method, url, headers=h, json=json, timeout=TIMEOUT, **kw)
        log_api(rid, method, url, resp.status_code, elapsed)  # 結構化 + 遮蔽(request-id §4.2)
        return _handle(resp, rid)                             # 見下方回應處理
    except httpx.TimeoutException as e:
        raise ApiError("請求逾時", status=None, request_id=rid) from e
    except httpx.TransportError as e:
        raise ApiError("連線失敗", status=None, request_id=rid) from e
    finally:
        set_current(None)
```

**認證方式(`auth` 參數)**
- `"bearer"`(業務 API 預設):帶 `Authorization: Bearer <JWT>`,token 由 **`lib/auth.py`** 提供(見 §5 接縫),api_client **不自行讀寫** `session_state`。
- `"cookie"`(introspection):**不帶 Bearer**,改轉發加密 session cookie(auth-flow §4.2);cookie 原始值由 `lib/auth.py` 從 `st.context.cookies` 取。
- `"none"`:公開端點(如健康檢查),兩者皆不帶。

**回應處理(`_handle`)**
- `204` / 空 body → 回 `None`(如 `delete_record`)。
- 2xx 且有 body → 解析 JSON。
- 非 2xx → 依 §3.2 映射例外(帶 `rid`)。

**其他**
- log 只記 `method`/`path`(去 query)/`status`/`elapsed_ms`/`request_id`;**絕不記** token/cookie/body(request-id §4.2)。
- 失敗例外一律帶 `request_id`。

---

## 5. 重試策略

兩種重試,語意不同,不可混淆:

| 類型 | 觸發 | 範圍 | 次數 |
|---|---|---|---|
| **auth reactive refresh** | 401 | **任何方法**(原請求未成功,重試安全);呼 `auth_lib.refresh_token()` 換新 token 再重試原請求 | **1 次**;仍 401 → `NotAuthenticated` |
| **網路重試** | 連線錯誤 / 逾時 / 502 / 503 / 504 | **僅冪等方法(GET)** | 最多 **2 次**,指數退避 + 抖動 |

- **auth 接縫**:api_client **不自行**做 introspection / 讀寫 token,而是呼叫 `lib/auth.py`:
  - `get_access_token() -> str`:取當前 JWT(來源 `session_state["access_token"]`)。
  - `refresh_token() -> str`:重呼 introspection、回寫 `session_state["access_token"]`、回傳新 token;仍失敗則拋 `NotAuthenticated`。
  - 如此 token 生命週期單點集中在 `auth.py`,api_client 只消費(見 auth-flow §4.3、§6)。
- **退避參數(可注入)**:base `0.2s`、factor `2`(→ 0.2s / 0.4s)、加 ±50% 抖動;**sleep 函式可注入**(預設 `time.sleep`,測試傳 no-op),使網路重試測試**不真的等待**。base/次數由 `lib/config.py` 設定。
- **非冪等**(POST/PUT/PATCH/DELETE,含新增/更新/刪除/批量匯入)**不自動重試**網路錯誤,避免重複寫入;交由使用者手動重試。
- 兩種重試各自產生**新的 `X-Request-ID`**(每次物理請求一個),便於在 log 追出重試鏈。

---

## 6. `ApiDataSource` ↔ REST 端點對應

實作 [`DataSource`](data-source.md#介面定義datasource);路徑為**假設預設**,實際**待與後端對齊**(§8)。

| 介面方法 | HTTP | 端點(假設) | 備註 |
|---|---|---|---|
| `list_records` | `GET` | `/records?page&size&category&keyword&sort` | 回 `{items, total, page, size}` → `Page` |
| `get_record` | `GET` | `/records/{id}` | 404 → `RecordNotFound` |
| `create_record` | `POST` | `/records` | body:`{title,value,category,note}`;`created_by`/時間戳由後端 |
| `update_record` | `PATCH` | `/records/{id}` | 403→`PermissionDenied`、404→`RecordNotFound` |
| `delete_record` | `DELETE` | `/records/{id}` | 204;軟刪除由後端 |
| `bulk_create` | `POST` | `/records/bulk` | body:`{rows:[...]}`;回 `{created, errors:[{row_index,reason}]}` → `ImportResult` |

- 查詢參數命名(`page`/`size`/`category`/`keyword`/`sort`)沿用 [data-source 介面約定](data-source.md#介面定義datasource);若後端命名不同,於本層轉換,**不外溢到頁面**。

---

## 7. 回應 ↔ 模型映射

- JSON → `Record`:欄位對映 `models.Record`;`created_at`/`updated_at` 以 ISO8601 解析為 `datetime`(UTC),`deleted_at` 可為 `None`。
- 缺欄位 / 型別不符 → 視為後端契約破壞,拋 `ApiError`(非 `ValidationError`,後者專指使用者輸入)。
- 映射集中在本層的 helper(如 `_to_record(json)`),便於單元測試與後端欄位改名時單點調整。

---

## 8. 相依 / 待確認

- [ ] **端點路徑與查詢參數命名**:§6 為假設,需與 FastAPI(StreamSightBackend)實際契約對齊。
- [ ] **錯誤封包格式**:§3.3 假設 `{"error":{code,message}}`,需與後端 / BFF 對齊(對應前端標準錯誤封包)。
- [ ] **`bulk_create` 端點形態**:批量建立是單一 `/records/bulk`,或逐筆呼叫 `/records`?影響部分成功語意(`ImportResult.errors`)。
- [ ] **分頁回應形狀**:`{items,total,page,size}` 欄位名需對齊後端。
- [x] **旗標交互**:`DATA_SOURCE=api` 需搭 `AUTH_MODE=bff`,無效組合啟動即拋錯(§1)。
- [x] **auth 接縫**:token 由 `lib/auth.py` 的 `get_access_token()` / `refresh_token()` 提供,api_client 只消費(§4、§5)——需在 [auth-flow §6](auth-flow.md#6-streamlit-端模組分層可測試性--tdd) 對應補這兩個函式。
- [x] **退避可測**:sleep 可注入,測試不等待(§5)。
- [ ] **`NotAuthenticated` 放置**:`lib/auth.py` 或 `lib/models.py`(與其他域例外同處)——實作時擇一。

---

## 9. 可測試性 / TDD

以 `httpx.MockTransport` 注入假回應,**不打真後端**;放 `tests/unit/test_api_client.py`:

1. **狀態映射** — 404→`RecordNotFound`、403→`PermissionDenied`、422→`ValidationError`、500→`ApiError(status=500)`。
2. **逾時 / 連線錯誤** — 轉 `ApiError(status=None)` 且帶 `request_id`。
3. **X-Request-ID** — 每次送出 headers 含之;兩次呼叫 ID 不同(解鎖 [Request ID 模組](request-id.md) §6 整合測 8–11)。
4. **log** — `streamsight.api` 出現結構化紀錄(含 `request_id`);**不含** token/cookie(遮蔽)。
5. **401 refresh** — 首次 401 → 呼(mock)`refresh_token()` 取新 token 重試一次;成功則回資料;再 401 → `NotAuthenticated`。
6. **網路重試** — GET 遇 503 重試至上限(**注入 no-op sleep**,不等待);POST 遇 503 **不重試**、直接 `ApiError`。
7. **`ApiDataSource` 映射** — `list_records` 組對查詢參數、解析 `Page`;`_to_record` 正確轉 `datetime`。
8. **認證方式** — 業務呼叫帶 `Bearer`;introspection 走 cookie 轉發、**不帶 Bearer**;`204` → 回 `None`。
9. **旗標交互** — `DATA_SOURCE=api` + `AUTH_MODE=mock` → `get_data_source()` 啟動即拋錯。

> 依 CLAUDE.md,逐一先寫失敗測試再補實作;所有測試 mock HTTP,不連 DB、不打真後端。

---

## 10. 檔案與掛載

```
lib/
├── api_client.py     # ApiError / ApiDataSource / _request 骨幹 / _to_record 映射
├── request_id.py     # X-Request-ID(§4 引用)
├── auth.py           # get_access_token() / refresh_token() / raw_cookie()(§4、§5 接縫)
├── models.py         # Record/Page/ImportResult + 域例外(§3.2 重用)
├── data_source.py    # DataSource 介面 + get_data_source()(api 時回 ApiDataSource;驗旗標組合)
└── config.py         # BFF/FastAPI base URL、cookie 名、逾時、重試/退避
tests/unit/test_api_client.py
```

> 於 [應用骨架 §6 lib 分層](app-skeleton.md#6-lib-分層總表單一入口地圖) 中 `lib/api_client.py` 的詳規即本檔;骨架必要性為**接 API 階段**(全 mock 下休眠)。
