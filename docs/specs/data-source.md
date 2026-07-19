# 規格:資料來源抽象層(Mock 先行,之後換 API)

本規格定義「資料管理頁」在**尚未接後端 API** 時,如何用 **mock data** 呈現,並確保日後換成真實 API **頁面零改動**。

- 適用頁面:[資料管理](pages/03-data-management.md)(可擴及其他 CRUD 頁)
- 前提架構:[ADR 0002](../decisions/0002-streamlit-as-api-client.md)(Streamlit 為 API Client,不直接連 DB)
- 上層骨架:[應用骨架 / 基礎架構](app-skeleton.md)(`get_data_source()` 由 `DATA_SOURCE` 旗標切換,身分 `Actor` 由骨架 `resolve_actor()` 提供)
- 真實實作:[API Client 規格](api-client.md)(`ApiDataSource` 實作本介面、REST 端點對應、錯誤映射)
- 相關:[前端頁面結構](frontend-pages.md)、[設計系統](design-system.md)

---

## 目標與非目標

**目標**
- 頁面能以假資料完整呈現列表 / 分頁 / 篩選 / 排序 / 新增 / 編輯 / 刪除 / 匯入的互動。
- mock 實作要能被單元測試(對齊 TDD),不是只回傳固定假陣列。
- 日後把資料來源換成 FastAPI REST,**只換一個實作類別**,頁面與測試邏輯不動。

**非目標**
- 不做真正的持久化(mock 資料僅存記憶體 / session,重啟即還原)。
- 不實作後端 API 本身。

---

## 核心設計:一個介面,兩種實作

在 `lib/` 定義單一資料存取介面 `DataSource`,頁面**只依賴此介面**;現在注入 `MockDataSource`,日後注入 `ApiDataSource`(即 `api_client`)。

```
pages/data_management.py ──► DataSource(介面 / Protocol)
                                 ├─ MockDataSource   ← 現在:記憶體假資料
                                 └─ ApiDataSource    ← 之後:呼叫 FastAPI(lib/api_client.py)
```

- 由工廠 `get_data_source()` 決定回傳哪個實作(依環境變數 / 設定旗標)。
- 頁面拿到的都是同型別,呼叫方式一致 → 切換來源時**頁面與行為測試不改**。

---

## 資料契約(型別定義)

以 `dataclass` 定義,為 mock 與 api 共用的資料形狀。**相容 Python 3.9**(型別註記用 `Optional[...]` / `List[...]`,或 `from __future__ import annotations`)。

```python
# lib/models.py(概念)
Role     = Literal["user", "admin"]
Category = Literal["感測器", "系統", "應用", "網路"]
CATEGORIES: list[str] = ["感測器", "系統", "應用", "網路"]   # selectbox 與種子共用
SORTABLE: list[str]   = ["id", "title", "value", "category", "created_at"]
DEFAULT_SORT = "id:asc"

class AdminRole:
    """後端 AdminRole IntEnum 對應數值（JWT grade claim 與 API admin_role 均為 int）。"""
    VIEWER      = 0
    EDITOR      = 50
    SUPER_ADMIN = 100
    ROOT        = 999   # 受保護 root；is_protected=True；能通過所有 SUPER_ADMIN gate

@dataclass
class Actor:              # 目前操作者(mock 由開發切換器提供;日後由認證提供)
    username: str
    role: Role               # "user" | "admin"
    grade: Optional[int] = None  # admin → AdminRole 數值 (0/50/100/999); user → None

@dataclass
class Record:
    id: int              # 1-based 自增(mock 由來源指派)
    title: str           # 必填,非空
    value: float
    category: str        # 需 ∈ CATEGORIES
    created_by: str      # username
    created_at: datetime # UTC
    updated_at: datetime # UTC
    note: str = ""       # 可選
    deleted_at: Optional[datetime] = None   # 軟刪除;None = 未刪除

@dataclass
class Page:
    items: list          # List[Record]
    total: int           # 篩選後總筆數(未分頁前)
    page: int            # 1-based
    size: int

@dataclass
class RowError:
    row_index: int       # 0-based(對應輸入檔第幾列)
    reason: str

@dataclass
class ImportResult:
    created: int
    errors: list         # List[RowError]
```

- **輸入資料**:`create_record` / `update_record` 接受的 `data` 僅含使用者可填欄位:`title, value, category, note`。`id / created_by / 時間戳 / deleted_at` 一律由來源端管理,前端不得指定。

### 權限純函式

本系統為 **admin-only**:所有登入者 `role == "admin"`,存取軸為 `grade`（`AdminRole` 數值：0/50/100/999 = viewer/editor/super_admin/root）;寫入一律限 `grade > AdminRole.VIEWER`（>0）。見[前端頁面結構 §存取控制](frontend-pages.md#存取控制本節為存取軸的單一真相)。

```python
def can_write(actor: Actor) -> bool:
    """寫入 gate(資料 CRUD 與系統管理提權操作共用)。grade > AdminRole.VIEWER → 可寫。"""
    if actor.role == "admin":
        return (actor.grade or 0) > AdminRole.VIEWER   # grade=0(viewer) → False
    return False                              # role == "user" 為 latent 分支(本部署不出現)

def can_edit(record: Record, actor: Actor) -> bool:
    """記錄層編輯權限。admin → 委派 can_write(去重,單一真相);user(latent) → 限創建者。"""
    if actor.role == "admin":
        return can_write(actor)
    return record.created_by == actor.username
```

- **`can_write` 是寫入權限的唯一真相**;`can_edit` 的 admin 分支一律委派 `can_write`,不重寫 `grade > AdminRole.VIEWER` 字面,避免兩處漂移。
- 供 mock 來源(擋寫入)與頁面(按鈕 `disabled`)共用、便於單元測試。
- 本部署下 `can_edit(record, actor) == can_write(actor)`(無 user role,創建者分支不觸發);系統管理頁只需 `can_write`(無 record)。

### 例外

| 例外 | 觸發 | 對應後端 |
|---|---|---|
| `RecordNotFound` | `get/update/delete` 遇不存在或已軟刪除的 `id` | 404 |
| `PermissionDenied` | `create/update/delete` 的 `actor` 無寫入權限（`grade == 0`，即 viewer；latent: 非創建者的 user） | 403 |
| `ValidationError` | 建立/更新欄位不合法(必填空、`category` 不在清單、`value` 非數) | 422 |

> 兩者為 `lib/` 自訂例外(避免與內建 `PermissionError` 混淆);頁面攔截後以 `st.error` / 停用按鈕呈現。

---

## 介面定義(`DataSource`)

以 `typing.Protocol` 定義,方法簽章即契約(mock 與 api 都需符合):

| 方法 | 簽章 | 說明 |
|---|---|---|
| 列表 | `list_records(page=1, size=20, category=None, keyword=None, sort="created_at:desc", include_deleted=False) -> Page` | 分頁/篩選/排序在來源端;預設濾掉軟刪除 |
| 單筆 | `get_record(record_id) -> Record` | 取單筆(編輯載入);不存在 → `RecordNotFound` |
| 建立 | `create_record(data, actor) -> Record` | 驗證欄位;自動帶 `created_by=actor.username` 與時間戳 |
| 更新 | `update_record(record_id, data, actor) -> Record` | 需權限,否則 `PermissionDenied`;更新 `updated_at` |
| 刪除 | `delete_record(record_id, actor) -> None` | 需權限;軟刪除(設 `deleted_at`) |
| 批量匯入 | `bulk_create(rows, actor) -> ImportResult` | 逐列驗證,合法即建立、非法進 `errors`,不中斷其餘 |

**參數約定**
- `page`:1-based;`size` 預設 20,UI 提供 20/50/100。
- `sort`:字串 `"欄位:asc|desc"`,`欄位` ∈ `SORTABLE`,預設 `id:asc`;非法欄位 → `ValidationError`。
- `category`:`None`=全部,否則需 ∈ `CATEGORIES`。
- `keyword`:對 `title` 子字串比對,**不分大小寫**;空字串視同無篩選。

---

## MockDataSource 行為規格

- **種子資料**:初始化時產生 **200 筆**決定性(固定,不用亂數)假 `Record`,平均分佈於四個分類、跨不同 `created_by`(見下方使用者)、跨時間範圍,讓分頁/篩選/排序看得出效果。
  - `created_at` 以固定基準日往回遞減(如 `2026-07-18T00:00:00Z` 減去 `i` 小時),避免用 `datetime.now()`(利於測試斷言)。
  - `created_by` 循環套用開發切換器的三個 username,確保「有的能編輯、有的停用」都演得到。
- **儲存位置**:記憶體。以 `st.session_state["mock_records"]` 保存,讓建立/更新/刪除在同一 session 內即時反映;重啟(或清 session)還原種子。純邏輯單元測試則直接 new 一個 `MockDataSource` 傳入初始清單,不依賴 Streamlit。
- **分頁**:先套篩選 → 排序 → 再依 `page`/`size` 切片;`total` 為**篩選後、分頁前**的筆數。
- **篩選**:`category` 精確比對;`keyword` 對 `title` 不分大小寫子字串比對;預設排除 `deleted_at` 非空者。
- **排序**:解析 `sort` 為(欄位, 方向)後排序;非法欄位 → `ValidationError`。
- **權限**:`update_record` / `delete_record` 以 `can_edit(record, actor)` 判斷,不通過 → `PermissionDenied`。
- **匯入**:見下方「匯入驗證規則」。

### 開發用使用者切換器(mock 專用)

mock 階段無認證,為了 demo 權限,於側邊欄提供切換器(僅 `DATA_SOURCE=mock` 時顯示):

| 選項 | username | role | grade | 用途 |
|---|---|---|---|---|
| Super Admin | `admin` | `admin` | `super_admin` | 可編輯/刪除任何資料（最高權限） |
| Editor | `editor` | `admin` | `editor` | 可編輯/刪除任何資料 |
| Viewer | `viewer` | `admin` | `viewer` | 唯讀，所有編輯/刪除按鈕停用 |

- 選擇結果寫入 `st.session_state["actor"]`(型別 `Actor`);頁面權限與 `create_record` 的 `created_by` 皆取自此。
- 種子資料的 `created_by` 循環套用 `alice` / `bob` / `admin`（mock 內部用名），確保列表有多筆不同創建者的資料。
- **此切換器為 mock 專屬**,換真實 API(改由認證提供 `Actor`)時移除。

### 匯入驗證規則(`bulk_create`)

- **接受格式**:CSV(含表頭)或 JSON(**物件陣列**)。
- **欄位**:`title`(必填、非空)、`value`(可轉 `float`)、`category`(需 ∈ `CATEGORIES`)、`note`(可選)。多餘欄位忽略。
- **逐列驗證**,任一不合法即記入 `errors`(`row_index` 為 0-based 輸入列序、`reason` 說明),**不中斷**其餘列。
- **上限**:單檔最多 **1000 列**,超過整體拒絕並提示。
- **重複**:mock 階段不做去重,合法列一律新建。
- 合法列以 `create_record` 相同規則寫入(自動帶 `created_by=actor.username` 與時間戳)。

---

## 頁面如何取用(注入點)

```python
# 概念示意,非最終碼
from lib.data_source import get_data_source

ds = get_data_source()          # 依 DATA_SOURCE 決定 mock / api
page = ds.list_records(page=1, size=20, category=sel, keyword=kw, sort=sort)
st.dataframe(page.items)
```

- 頁面不 import 任何具體實作,只透過 `get_data_source()`。
- **切換旗標**:環境變數 `DATA_SOURCE`,值 `mock`(預設)或 `api`;`get_data_source()` 依此回傳對應實作。
- 測試可注入 mock(或直接 new `MockDataSource`)驗證頁面行為。

---

## 換成真實 API 時要改什麼

| 項目 | Mock 階段 | 換 API 後 |
|---|---|---|
| 資料來源 | `MockDataSource` | `ApiDataSource`(用 `lib/api_client.py` 呼叫 FastAPI) |
| 切換點 | `get_data_source()` 回傳 mock | 改回傳 api 實作(或依旗標) |
| 頁面 `pages/data_management.py` | — | **不改** |
| 介面 `DataSource` / 型別 | — | **不改** |
| 頁面行為測試(AppTest) | 對 mock | **不改**(仍可對 mock 或 stub) |
| 權限純函式 `can_edit` / 型別 / 例外 | — | **不改**(api 實作沿用同契約) |
| 開發用使用者切換器 | 側邊欄顯示 | **移除**;`Actor` 改由認證(Design B)提供 |

> 唯一新增的是 `ApiDataSource` 的實作與其單元測試(mock HTTP 回應),既有邏輯與頁面不受影響。

---

## 檔案配置(規劃)

```
lib/
├── models.py          # Actor / Record / Page / ImportResult / RowError + CATEGORIES + can_edit() + 例外
├── data_source.py     # DataSource(Protocol) + get_data_source() 工廠(讀 DATA_SOURCE)
├── mock_data_source.py# MockDataSource(記憶體假資料,含 200 筆決定性種子)
└── api_client.py      # (日後) ApiDataSource:呼叫 FastAPI
pages/
└── data_management.py # 薄頁面,只呼叫 get_data_source();mock 時掛開發用切換器
```

---

## 對齊 TDD 的落地順序

依 CLAUDE.md「先失敗測試 → 最少實作 → 重構」,建議行為切分(每項先寫 RED):

> **✅ = 已有測試且通過；❌ = 待補失敗測試**

1. ✅ `can_edit(record, actor)` — Admin 恆真;創建者為真;他人為假。（`tests/unit/test_models.py`）
2. ✅ `MockDataSource.list_records` — 種子 200 筆、分頁切片、`total` 為篩選後筆數、預設排除軟刪除。（`tests/unit/test_mock_data_source.py`）
3. ✅ 篩選 — `category` 精確、`keyword` 不分大小寫子字串。（`tests/unit/test_mock_data_source.py`）
4. ✅ 排序 — 依 `sort` 欄位/方向正確;非法欄位拋 `ValidationError`。（`tests/unit/test_mock_data_source.py`）
5. ✅ `create_record` — 欄位驗證;自動帶 `created_by`/時間戳;`total` +1。（`tests/unit/test_mock_data_source.py`）
6. ✅ `update_record` / `delete_record` — 有權限成功(軟刪除設 `deleted_at`、更新改 `updated_at`);無權限拋 `PermissionDenied`;不存在拋 `RecordNotFound`。（`tests/unit/test_mock_data_source.py`）
7. ✅ `bulk_create` — 合法列建立、非法列進 `errors`(不中斷)、超過 1000 列整體拒絕。（`tests/unit/test_mock_data_source.py`）
8. ✅ 頁面(AppTest + 匯入 unit)— 篩選、分頁、新增/編輯/刪除彈窗、匯入解析（`tests/app/test_data_management.py`、`tests/unit/test_import_utils.py`，見 [03-data-management.md § TDD 落地順序 8-1~8-8](pages/03-data-management.md#本頁-tdd-落地順序承接-data-sourcemd-第-8-步)）

- 純邏輯測試放 `tests/unit/`,頁面行為放 `tests/app/`。

---

## 風險與備註

- mock 資料**不持久化**:示範 / 開發用途,不可誤當正式資料。
- 介面若日後不敷使用(如需游標分頁 / 部分更新),**同步修改 `DataSource` 與所有實作**,避免 mock 與 api 契約分歧。
- 切換旗標(mock ↔ api)建議走設定(環境變數),避免在頁面散寫判斷。
