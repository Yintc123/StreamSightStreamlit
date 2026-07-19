# 規格：Records API 串接（資料管理 / 資料分析）

- 對應頁面：`pages/data_management.py`、`pages/analytics.py`
- 對應模組：`lib/api_client.py`（`ApiDataSource`）、`lib/data_source.py`
- 後端 Base URL：`{FASTAPI_BASE_URL}`（設定項 `fastapi_base_url`，見 [config.md](config.md)）
- 認證方式：**Bearer JWT（Admin，min=VIEWER）**；token 由 `lib/auth.get_access_token()` 提供，`ApiClient` 自動附帶；401 時由 `ApiClient` 自動觸發 reactive refresh（見 [api-client.md](api-client.md)）

---

## 1. 前提確認

### 1.1 已完成的實作

| 元件 | 狀態 | 說明 |
|---|---|---|
| `ApiClient`（`lib/api_client.py`） | ✅ 已完整 | Bearer JWT、401 reactive refresh、逾時重試、錯誤轉譯 |
| `ApiDataSource`（`lib/api_client.py`） | ✅ 已完整 | 實作全部 `DataSource` 方法，對應後端 `/records/*` |
| `get_data_source()`（`lib/data_source.py`） | ✅ 已完整 | `USE_MOCK=false` 時自動切換至 `ApiDataSource` |
| `_to_record()`（`lib/api_client.py`） | ✅ 已完整 | 後端 JSON `RecordSummary` → 前端 `Record` |

**啟動 API 模式只需設定兩個環境變數**（見 §6），不需改程式碼——**前提是先解決 §4 的已知缺口**。

### 1.2 後端認證分層

後端 JWT claims 中 `role=1`（Admin）+ `grade`（等級 rank）。Streamlit 持有的 access token 由 BFF 換取，格式已在 [auth-flow.md](auth-flow.md) 定義，此處不重複。

---

## 2. 資料管理頁（`pages/data_management.py`）端點對應

| 頁面操作 | `DataSource` 方法 | HTTP | 後端路徑 | 認證最低要求 |
|---|---|---|---|---|
| 列表（篩選 / 排序 / 分頁） | `list_records(page, size, category, keyword, sort)` | `GET` | `/records` | VIEWER (0) |
| 取單筆（編輯 dialog） | `get_record(record_id)` | `GET` | `/records/{id}` | VIEWER (0) |
| 新增 | `create_record(data, actor)` | `POST` | `/records` | EDITOR (50) |
| 更新（全量替換 4 欄） | `update_record(record_id, data, actor)` | `PATCH` | `/records/{id}` | EDITOR (50) |
| 刪除（軟刪除） | `delete_record(record_id, actor)` | `DELETE` | `/records/{id}` | EDITOR (50) |
| 批次匯入 | `bulk_create(rows, actor)` | `POST` | `/records/bulk` | EDITOR (50) |

### 2.1 `GET /records` 查詢參數對應

| 前端 `_SORT_OPTIONS` 值 | 後端 `sort` 參數 | 後端支援 |
|---|---|---|
| `id:asc` / `id:desc` | 同左 | ✅ |
| `created_at:asc` / `created_at:desc` | 同左 | ✅ |
| `title:asc` / `title:desc` | 同左 | ✅ |
| `value:asc` / `value:desc` | 同左 | ✅ |
| `category:asc` / `category:desc` | 同左 | ✅ |

後端 `RecordSortField` enum 包含 `id / title / value / category / created_at`；`SortDirection` 包含 `asc / desc`；解析格式為 `{field}:{direction}`。**前端所有排序選項與後端完全相容，無需修改。**

### 2.2 後端 size 夾值規則（資料管理頁）

後端 service 對 **無日期範圍** 請求套用 `records_list_max_page_size`（預設 **100**）。前端分頁選項為 20 / 50 / 100，均在此範圍內，**不會被夾值截斷**。

### 2.3 回應欄位對應（`RecordSummary` → `Record`）

| 後端欄位 | 前端 `Record` 欄位 | 說明 |
|---|---|---|
| `id` | `id` | int |
| `title` | `title` | str |
| `value` | `value` | float |
| `category` | `category` | str（後端由 category_id JOIN name 解析） |
| `created_by` | `created_by` | str（後端由 principal_id JOIN username 解析） |
| `created_at` | `created_at` | datetime（ISO 8601，`_parse_dt` 正規化） |
| `updated_at` | `updated_at` | datetime |
| `note` | `note` | str（可為 ""） |
| `deleted_at` | `deleted_at` | datetime \| None（軟刪除標記） |

### 2.4 `PATCH /records/{id}`（更新）語意

後端 `RecordUpdate` 是**全量替換** `title / value / category / note` 四欄，非 partial update。前端 `_edit_dialog` 同樣以表單全量送出，**語意一致**。

---

## 3. 資料分析頁（`pages/analytics.py`）端點對應

分析頁所有資料來源為 `list_records`，僅使用讀取路徑。

| 操作 | 方法 | 後端路徑 | 備註 |
|---|---|---|---|
| 拉取全量資料 | `list_records(page=1, size=N, category=..., date_from=..., date_to=...)` | `GET /records` | **見 §4.1 缺口說明** |

---

## 4. 串接前必須解決的缺口

### 4.1 ⚠️ 關鍵：analytics 的 `size=1000` 會被夾至 100

**問題**：`analytics.py` 目前呼叫 `ds.list_records(page=1, size=1000)`，不帶日期參數。後端對**無日期範圍**請求套用 `records_list_max_page_size=100`，silently 夾值至 100 筆，導致分析圖表資料不完整。

**後端規則（service 邏輯）**：
```
max_size = records_analytics_max_page_size (預設 5000)  # 若帶 date_from 或 date_to
           records_list_max_page_size      (預設 100)   # 否則
size = min(max(size, 1), max_size)
```

**解法**：`analytics.py` 改為**伺服器端日期篩選**——把 `filter_bar` 已蒐集的 `fp.date_from` / `fp.date_to` 傳給後端，換取 analytics_max（5000）上限，同時讓後端做日期過濾。需要以下步驟（TDD）：

**步驟 A — 擴展 `DataSource` protocol（`lib/data_source.py`）**

```python
def list_records(
    self,
    page: int = 1,
    size: int = 20,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    sort: str = DEFAULT_SORT,
    include_deleted: bool = False,
    date_from: Optional[date] = None,   # ← 新增
    date_to: Optional[date] = None,     # ← 新增
) -> Page: ...
```

**步驟 B — 更新 `ApiDataSource.list_records`（`lib/api_client.py`）**

```python
if date_from:
    params["date_from"] = date_from.isoformat()
if date_to:
    params["date_to"] = date_to.isoformat()
```

後端 `date_from` = 含起始 00:00:00 UTC；`date_to` = 含當天末（推進至隔日 00:00:00）。

**步驟 C — 更新 `analytics.py`**

```python
result = ds.list_records(
    page=1,
    size=5000,
    category=category_param,
    date_from=fp.date_from,   # 伺服器端篩選
    date_to=fp.date_to,
)
df = records_to_df(result.items)  # 不再需要 client-side filter_by_date
```

`MockDataSource` 亦需新增 `date_from` / `date_to` 參數（支援 mock 模式正確運作）。

### 4.2 分類（Categories）仍為硬編碼

**現況**：`data_management.py` 與 `analytics.py` 使用 `lib/models.py` 的靜態 `CATEGORIES` 常數。

**後端提供**：`GET /records/categories` → `Category[]`（name, label, sort_order）；僅回傳 `is_active=True` 的分類。

**建議**：Phase 1 維持硬編碼可接受（分類不易變動）。接 API 後若需動態分類：
- 在 `DataSource` 加 `list_categories() -> list[str]`
- 用 `@st.cache_data(ttl=300)` 快取，避免每次 rerun 重查

**Phase 1 決策：保持硬編碼，不列為上線阻斷項。**

---

## 5. 後端錯誤碼對應

`ApiClient._handle()` 已將後端 HTTP 狀態映射為前端例外，頁面以 `render_error(exc)` 統一呈現（見 [error-handling.md](error-handling.md)）。

| 後端狀態碼 | 前端例外 | 頁面呈現 |
|---|---|---|
| 400 / 422 | `ValidationError` | `st.error(message)` |
| 401 | `NotAuthenticated` → app.py 攔截 → 重導登入 | meta refresh |
| 403 | `PermissionDenied` | `st.error(message)` |
| 404 | `RecordNotFound` | `st.warning`（dialog 內）|
| 502 / 503 / 504 | `ApiError`（GET 自動重試 2 次） | `st.error` + request_id |
| 逾時 / 連線錯誤 | `ApiError(status=None)` | `st.error` + request_id |

---

## 6. 環境設定（上線前必填）

修改 `.env`：

```env
USE_MOCK=false
FASTAPI_BASE_URL=https://<backend-host>
```

其餘已有預設值的設定項見 [config.md](config.md)：

| 設定項 | 預設值 | 說明 |
|---|---|---|
| `HTTP_CONNECT_TIMEOUT_SECONDS` | 5 | httpx connect timeout |
| `HTTP_READ_TIMEOUT_SECONDS` | 30 | httpx read timeout |
| `HTTP_RETRY_MAX` | 2 | GET 失敗最多重試次數 |
| `HTTP_RETRY_BASE_SECONDS` | 0.2 | 重試初始退避秒數 |
| `HTTP_RETRY_FACTOR` | 2.0 | 指數退避係數 |

---

## 7. TDD 計畫

依 CLAUDE.md，所有實作前先寫失敗測試。優先順序：

### 7.1 `DataSource` protocol 擴展（`tests/unit/test_data_source.py`）

1. `MockDataSource.list_records(date_from=date(2024,1,1), date_to=date(2024,12,31))` → 只回傳範圍內記錄。
2. `MockDataSource.list_records(date_from=None, date_to=None)` → 行為與現有相同（回歸）。

### 7.2 `ApiDataSource` 日期參數（`tests/unit/test_api_client.py`）

3. `ApiDataSource.list_records(date_from=date(2024,1,1))` → 請求帶 `date_from=2024-01-01`。
4. `ApiDataSource.list_records(date_to=date(2024,12,31))` → 請求帶 `date_to=2024-12-31`。
5. `ApiDataSource.list_records(date_from=None, date_to=None)` → 請求**不帶** `date_from` / `date_to`（回歸：不傳空值給後端）。
6. `ApiDataSource.list_records(size=5000, date_from=date(2024,1,1))` → params 含 `size=5000`（analytics 大批量路徑）。

### 7.3 分析頁整合行為（`tests/app/test_analytics.py`，AppTest）

7. mock 模式：`analytics.py` 帶日期篩選 → `df` 僅含範圍內資料（驗證伺服器端篩選路徑）。
8. mock 模式：無日期篩選 → 全量資料（回歸）。

---

## 8. 串接驗收清單

上線前人工驗證（自動化測試無法覆蓋的 E2E 路徑）：

- [ ] `USE_MOCK=false` 啟動後，資料管理頁列表正常顯示後端資料
- [ ] 篩選（分類 / 關鍵字 / 排序）結果與後端一致
- [ ] 新增 / 編輯 / 刪除後列表即時反映（rerun 重查）
- [ ] CSV / JSON 匯入：成功筆數 + 錯誤行數顯示正確
- [ ] 分析頁：帶日期篩選時圖表資料正確；不帶日期時全量資料正確（§4.1 缺口已修）
- [ ] VIEWER 帳號：新增 / 編輯 / 刪除按鈕為 disabled（`can_write(actor)` 邏輯對齊後端 EDITOR+ 要求）
- [ ] token 過期時 reactive refresh 成功（用戶無感知）
- [ ] 後端 422 時前端顯示後端錯誤訊息而非通用文字
