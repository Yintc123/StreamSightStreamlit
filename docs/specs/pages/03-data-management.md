# 頁面規格:資料管理(UI 規格)

- 頁面編號:3
- 對應模組:模組 2 資料管理
- URL 路徑:`/data_management`(`st.Page(..., url_path="data_management", default=True)`;併帶預設落地頁,根路徑 `/` 與未匹配路徑（404）皆 fallback 至此)
- 存取權限:已登入皆可讀取;**寫入限 `grade > AdminRole.VIEWER`**（>0；super_admin/root/editor 可寫，viewer=0 唯讀）。本系統為 admin-only，存取軸為 grade，見[前端頁面結構 §存取控制](../frontend-pages.md#存取控制本節為存取軸的單一真相)。
- 導覽:所有登入者可見
- 相關:[前端頁面結構](../frontend-pages.md)、[設計系統](../design-system.md)、[功能能力對照](../feature-capability.md)、[資料來源抽象層(Mock 先行)](../data-source.md)、[ADR 0002](../decisions/0002-streamlit-as-api-client.md)

## 目的

提供資料的建立(C)、讀取(R)、更新(U)、刪除(D)與批量匯入(CSV/JSON),並以權限控制編輯與刪除。**所有資料存取一律經 `lib/api_client.py` 呼叫 FastAPI,前端不直接連 DB。**

> **開發策略**:第一階段先以 **mock data** 呈現(不接後端),資料來源抽象為 `DataSource` 介面,頁面只依賴介面;日後換真實 API 時頁面零改動。詳見[資料來源抽象層規格](../data-source.md)。

---

## 開發階段劃分

### Phase 1 — Mock 階段（當前目標）

**前提**：`MockDataSource` 全部 CRUD 邏輯（TDD 步驟 1–7）已完成，可直接呼叫。

**本階段交付範圍**：

| # | 功能 | 說明 |
|---|---|---|
| 1 | `st.tabs` 三分頁骨架 | 列表 / 新增 / 匯入容器 |
| 2 | 篩選 + 排序連線 | 工具列四元件 → `list_records(category, keyword, sort)` |
| 3 | 分頁連線 | `pagination_controls` → `list_records(page, size)` |
| 4 | 新增表單 | `st.form` → `create_record` → `st.rerun()` |
| 5 | 編輯彈窗 | `@st.dialog` + session_state trigger → `update_record` → `st.rerun()` |
| 6 | 刪除確認彈窗 | `@st.dialog` + session_state trigger → `delete_record` → `st.rerun()` |
| 7 | 匯入分頁 | `st.file_uploader` → `bulk_create` → 錯誤列標示 |

**Mock 階段不做**（留給 Phase 2）：
- 真實後端 HTTP 呼叫（`ApiDataSource`）
- JWT 認證驗證（由認證模組處理）
- `st.cache_data` 快取層
- 側邊欄切換器移除（換真實 auth 後才移）

**Mock 階段完成判準**：
> `pytest tests/app/test_data_management.py` 全數通過（含 TDD 8-2 ～ 8-8），`DATA_SOURCE=mock` 下頁面三個分頁可完整操作。

### Phase 2 — API 接入（Mock 完成後）

唯一改動：環境變數 `DATA_SOURCE=api`，`get_data_source()` 切換至 `ApiDataSource`。**頁面程式碼零改動。**

---

## 頁面骨架（Mock 階段 pages/data_management.py）

```python
import pandas as pd
import streamlit as st

from lib import state
from lib.data_source import get_data_source
from lib.errors import render_error
from lib.import_utils import parse_csv_bytes, parse_json_bytes, summarize_import
from lib.models import CATEGORIES, DEFAULT_SORT, RecordNotFound, can_edit
from lib.ui import empty_state, pagination_controls

# ── module-level：dialog 函式必須在最頂層定義 ────────────────────
ds = get_data_source()
actor = state.get_actor()

@st.dialog("編輯資料")
def _edit_dialog(record_id: int) -> None: ...   # 詳見「編輯」小節

@st.dialog("確認刪除")
def _delete_dialog(record_id: int) -> None: ... # 詳見「刪除」小節

# ── trigger 檢查（每次 rerun 最優先執行）────────────────────────
# pop()：一次性消費，防止 X 關閉後的下次 rerun 重開 dialog。
# @st.dialog 基於 @st.fragment，dialog 內部互動走 fragment rerun，
# 不過 trigger check，dialog 仍保持開啟。
if "dm_edit_id" in st.session_state:
    _edit_dialog(st.session_state.pop("dm_edit_id"))
if "dm_delete_id" in st.session_state:
    _delete_dialog(st.session_state.pop("dm_delete_id"))

# ── 頁面主體 ─────────────────────────────────────────────────────
st.title("資料管理")
list_tab, create_tab, import_tab = st.tabs(["列表", "新增", "匯入"])

_SORT_OPTIONS = {
    "ID ↑":      "id:asc",
    "ID ↓":      "id:desc",
    "建立時間 ↓": "created_at:desc",
    "建立時間 ↑": "created_at:asc",
    "標題 ↑":    "title:asc",
    "標題 ↓":    "title:desc",
    "數值 ↑":    "value:asc",
    "數值 ↓":    "value:desc",
    "分類 ↑":    "category:asc",
    "分類 ↓":    "category:desc",
}

with list_tab:
    st.session_state.setdefault("dm_category", "全部")
    st.session_state.setdefault("dm_keyword",  "")
    st.session_state.setdefault("dm_sort",     "ID ↑")
    st.session_state.setdefault("dm_size",     20)

    cat_area, sort_area, size_area, form_area = st.columns([2, 2, 1, 3], vertical_alignment="center")
    with cat_area:
        cat_val = st.selectbox("分類", ["全部"] + CATEGORIES, key="dm_category")
    with sort_area:
        sort_label = st.selectbox("排序", list(_SORT_OPTIONS), key="dm_sort")
    with size_area:
        size = st.selectbox("每頁筆數", [20, 50, 100], key="dm_size")
    with form_area:
        with st.form("dm_filter_form"):
            col_kw, col_btn = st.columns([3, 1], vertical_alignment="center")
            with col_kw:
                kw_val = st.text_input("關鍵字", key="dm_keyword")
            with col_btn:
                st.form_submit_button("搜尋", use_container_width=True)

    # 篩選條件改變時重置頁碼
    _prev = st.session_state.get("dm_prev_filter")
    _cur  = (cat_val, kw_val)
    if _prev is not None and _prev != _cur:
        st.session_state["dm_page"] = 1
    st.session_state["dm_prev_filter"] = _cur
    category = None if cat_val == "全部" else cat_val
    page = st.session_state.get("dm_page", 1)

    result = ds.list_records(
        page=page, size=size,
        category=category,
        keyword=kw_val,
        sort=_SORT_OPTIONS[sort_label],
    )

    if result.total == 0:
        empty_state("目前範圍內沒有資料")
    else:
        header = st.columns([1, 3, 1, 1, 1, 2, 2, 1, 1], vertical_alignment="bottom")
        header[0].caption("ID")
        header[1].caption("標題")
        header[2].caption("數值")
        header[3].caption("分類")
        header[4].caption("創建者")
        header[5].caption("建立時間")
        header[6].caption("更新時間")
        st.divider()
        for record in result.items:
            col_id, col_title, col_value, col_cat, col_creator, \
            col_created, col_updated, col_edit, col_del = \
                st.columns([1, 3, 1, 1, 1, 2, 2, 1, 1])
            col_id.write(record.id)
            col_title.write(record.title)
            col_value.write(f"{record.value:.2f}")
            col_cat.write(record.category)
            col_creator.write(record.created_by)
            col_created.write(record.created_at.strftime("%Y-%m-%d %H:%M"))
            col_updated.write(record.updated_at.strftime("%Y-%m-%d %H:%M"))
            editable = actor is not None and can_edit(record, actor)
            if col_edit.button("編輯", key=f"dm_edit_{record.id}", disabled=not editable):
                st.session_state["dm_edit_id"] = record.id
                st.rerun()
            if col_del.button("刪除", key=f"dm_delete_{record.id}", disabled=not editable):
                st.session_state["dm_delete_id"] = record.id
                st.rerun()
        pagination_controls(result.total, size, key_prefix="dm")

with create_tab:
    with st.form("dm_create", clear_on_submit=True):
        title    = st.text_input("標題")
        value    = st.number_input("數值", format="%.2f")
        category = st.selectbox("分類", CATEGORIES)
        note     = st.text_area("備註")
        submitted = st.form_submit_button("送出")
    if submitted:
        if not title.strip():
            st.error("標題為必填")
        else:
            try:
                ds.create_record(
                    {"title": title, "value": value, "category": category, "note": note},
                    actor,
                )
                st.toast("已新增")
                st.rerun()
            except Exception as exc:
                render_error(exc)   # ValidationError / ApiError 等一律依 error-handling §3

with import_tab:
    ...   # 詳見「分頁三：匯入」小節
```

> 這是**完整骨架**，與 `pages/data_management.py` 保持同步；各 dialog 內容詳見對應小節。

### 最佳實踐說明

| 規則 | 說明 |
|---|---|
| **Dialog trigger pattern（一次性 pop）** | 按鈕點擊寫入 `st.session_state["dm_edit_id"]`（或 `dm_delete_id`）並 `st.rerun()`；頁面頂端的 trigger 檢查以 **`pop()`** 一次性消費 key 並呼叫 dialog。`@st.dialog` 基於 `@st.fragment`，dialog 內部互動走 **fragment rerun**，不經過 trigger check，dialog 仍保持開啟。當使用者按 X 關閉時，觸發 full page rerun，此時 key 已被消費，不再重開 dialog。**若在 AppTest 測試多步驟 dialog 互動**（如 submit），因 AppTest 無 fragment rerun，需在每次 dialog-required run 前手動 `at.session_state["dm_edit_id"] = record_id` 重新設定。 |
| **Dialog 函式在 module 頂層** | `@st.dialog` 裝飾的函式只能定義在 module 頂層（非 `with tab:` 內），否則 Streamlit 報錯。 |
| **ds / actor 取自 module scope** | Dialog 函式不需接收 `ds` / `actor` 參數，直接取 module-level 變數即可。 |
| **篩選變動才重置頁碼** | 比對 `dm_prev_filter`（`(cat_val, kw_val)` tuple），只在值確實改變時才重置 `dm_page = 1`。 |
| **分類 / 排序 / 每頁筆數即時觸發** | 三者在 form 外，改動立即 rerun 並重查。關鍵字需按「搜尋」才套用（`st.form` 包裹）。 |
| **DataSource 呼叫一律包 try/except → `render_error`** | **所有** `ds.*` 呼叫（讀取與 mutation：list/get/create/update/delete/bulk）都以 `except Exception as exc: render_error(exc)` 收斂——api 模式下任何呼叫都可能拋 `ApiError` / `PermissionDenied` 等，Streamlit **沒有全域錯誤邊界**，未攔截的例外會變成 traceback 畫面。錯誤層級 / 文案 / request_id 由 [error-handling.md §3](../error-handling.md) 統一（`NotAuthenticated` 由 `render_error` re-raise 交 app.py 導向）。dialog 內失敗保留 dialog 可重試；頁面級失敗保留頁框可重試。 |
| **`st.rerun()` 只用於 mutation 後** | 寫入成功後才呼叫，不做「防禦性 rerun」。 |

---

## Session State 鍵總表（本頁 `dm_*`）

> 所有本頁擁有的 session_state key 一律以 `dm_` 為前綴，避免與其他頁面衝突。

| Key | 型別 | 管理者 | 說明 |
|---|---|---|---|
| `dm_page` | `int` | `pagination_controls` | 當前頁碼（1-based） |
| `dm_prev` | `bool` | `pagination_controls` | 上一頁按鈕狀態（內部） |
| `dm_next` | `bool` | `pagination_controls` | 下一頁按鈕狀態（內部） |
| `dm_category` | `str` | 頁面 selectbox | 分類篩選值；改動即時重查 |
| `dm_keyword` | `str` | form `st.text_input` | 關鍵字；需按「搜尋」才套用 |
| `dm_sort` | `str` | 頁面 selectbox | 排序選項標籤（對應 `_SORT_OPTIONS` key）；改動即時重查；預設 `"ID ↑"` |
| `dm_size` | `int` | 頁面 selectbox | 每頁筆數（20/50/100）；改動即時重查 |
| `dm_prev_filter` | `tuple[str, str]` | 頁面 | `(cat_val, kw_val)` 快照，用於偵測變動並重置頁碼 |
| `dm_edit_id` | `int` | 頁面按鈕 | Dialog trigger：寫入後 rerun 開啟編輯 dialog；trigger check 以 `pop()` 一次性消費，dialog 開啟後 key 即消失（不需在 dialog 內刪除） |
| `dm_delete_id` | `int` | 頁面按鈕 | Dialog trigger：寫入後 rerun 開啟刪除 dialog；trigger check 以 `pop()` 一次性消費，同上 |
| `dm_import_rows` | `list[dict]` | 「確認匯入」按鈕 | 匯入 trigger：按下後寫入解析結果並 `st.rerun()`，匯入分頁的 trigger 區塊以 `pop()` 消費並執行 `bulk_create`（AppTest 不支援 file_uploader，可直接注入此 key 驅動匯入路徑） |
| `dm_import_result` | `ImportResult` | 匯入 trigger 區塊 | flash：匯入成功後存入並 `st.rerun()` 刷新列表；下一輪由匯入分頁頂端 `pop()` 顯示成功 / 部分錯誤訊息（避免訊息被 rerun 沖掉） |

---

## 已實作元件（直接 import 使用）

> 所有元件均有完整測試覆蓋，**直接呼叫，不需重複實作**。

### lib/ui.py

| 元件 | 簽章 | 用途 |
|---|---|---|
| `FilterParams` | `@dataclass(category, keyword, date_from, date_to)` | 篩選條件快照（本頁工具列以 tuple 比對；`filter_bar` 呼叫者使用此型別） |
| `filter_bar()` | `filter_bar(categories, key_prefix, show_date=True, show_keyword=True) -> FilterParams` | 通用篩選列 UI；本頁工具列採用更彈性的內嵌佈局，未直接使用 |
| `pagination_controls()` | `pagination_controls(total, size, key_prefix) -> int` | 上/下頁按鈕 + caption；total==0 靜默；回傳當前頁碼（1-based） |
| `empty_state()` | `empty_state(message) -> None` | 無資料時的 `st.info` 包裝 |
| `metric_cards()` | `metric_cards(metrics: List[Metric]) -> None` | N 欄指標卡（統計摘要用） |
| `Metric` | `@dataclass(label, value, delta, delta_color, help)` | 指標卡資料 |

### lib/models.py

| 元件 | 說明 |
|---|---|
| `Record` | 資料記錄（id, title, value, category, created_by, created_at, updated_at, note, deleted_at） |
| `Actor` | 操作者（`username: str`、`role: Role`、`grade: Optional[int] = None`）。`grade` 對應後端 JWT `grade` claim（`AdminRole` 數值）：admin → `0`/`50`/`100`/`999`；user → `None` |
| `Page` | 分頁結果（items, total, page, size） |
| `ImportResult` | 匯入結果（created, errors: List[RowError]） |
| `RowError` | 匯入錯誤（row_index, reason） |
| `CATEGORIES` | `["感測器", "系統", "應用", "網路"]`（selectbox 直接用） |
| `SORTABLE` | `["id", "title", "value", "category", "created_at"]` |
| `DEFAULT_SORT` | `"id:asc"` |
| `can_write(actor)` | 寫入 gate 唯一真相：admin + `grade > AdminRole.VIEWER`（>0）→ True；viewer（0）→ False。新增/匯入/編輯/刪除共用 |
| `can_edit(record, actor)` | 記錄層編輯權限；admin 分支**委派 `can_write`**；user(latent) → `created_by == actor.username` |
| `RecordNotFound` | 404 例外 |
| `PermissionDenied` | 403 例外 |
| `ValidationError` | 422 例外 |

### lib/state.py

| 函式 | 說明 |
|---|---|
| `get_actor() -> Actor \| None` | 從 session_state 取當前操作者 |
| `set_actor(actor)` | 寫入 session_state |

### lib/data_source.py

| 函式 | 說明 |
|---|---|
| `get_data_source() -> DataSource` | 依 `DATA_SOURCE` 環境變數回傳 MockDataSource 或 ApiDataSource |

### lib/import_utils.py

| 函式 | 說明 |
|---|---|
| `parse_csv_bytes(content: bytes) -> tuple[list[dict], str \| None]` | 解析 CSV bytes，回傳 `(rows, error_msg)`；error_msg 為 None 表示成功 |
| `parse_json_bytes(content: bytes) -> tuple[list[dict], str \| None]` | 解析 JSON bytes，同上 |
| `summarize_import(result: ImportResult) -> tuple[str, str, str \| None]` | 匯入結果 → `(level, message, detail)` 顯示三元組；全成功 `("success", …, None)`，有錯誤列 `("warning", …, "錯誤列：…")`（1-based，前 5 列） |

---

## 實作進度（當前狀態）

| 功能 | 狀態 | 備註 |
|---|---|---|
| 列表展示（9 欄逐列佈局） | ✅ 完成 | ID / 標題 / 數值 / 分類 / 創建者 / 建立時間 / 更新時間 / 編輯 / 刪除 |
| 權限控制（按鈕 disabled） | ✅ 完成 | `can_edit()` 含 grade=viewer 唯讀邏輯 + AppTest 覆蓋 |
| 開發用 Actor 切換器（側邊欄） | ✅ 完成 | Super Admin / Editor / Viewer 三種 admin |
| `st.tabs` 三分頁容器 | ✅ 完成 | 列表 / 新增 / 匯入 |
| 工具列（分類 / 排序 / 每頁筆數 / 關鍵字+搜尋） | ✅ 完成 | 前三即時觸發；關鍵字需按「搜尋」 |
| 排序傳入 `list_records` | ✅ 完成 | `_SORT_OPTIONS`，預設 `"id:asc"` |
| 新增分頁（`st.form`） | ✅ 完成 | 驗證 + `st.rerun()` |
| 編輯彈窗（`@st.dialog`） | ✅ 完成 | session_state trigger pattern（dm_edit_id） |
| 刪除確認彈窗（`@st.dialog`） | ✅ 完成 | session_state trigger pattern（dm_delete_id） |
| 匯入分頁（CSV/JSON） | ✅ 完成 | `lib/import_utils.py` + `bulk_create` |

---

## 版面總覽

標準寬度單欄,頁首 + `st.tabs` 三分頁:

```
┌──────────────────────────────────────────────────────────────┐
│ 資料管理                                                        │  ← st.title
├──────────────────────────────────────────────────────────────┤
│ [ 列表 ]   [ 新增 ]   [ 匯入 ]                                  │  ← st.tabs
└──────────────────────────────────────────────────────────────┘
側邊欄(僅 mock):[目前使用者 ▾ Super Admin / Editor / Viewer]     ← 開發用切換器（三種 Admin）
```

| 分頁 | 目的 | 對應 CRUD |
|---|---|---|
| 列表 | 讀取、篩選、排序、分頁、逐列編輯/刪除 | R / U / D 入口 |
| 新增 | 單筆建立 | C |
| 匯入 | CSV / JSON 批量建立 | C(批量) |

> **目前使用者(Actor)**：mock 階段由側邊欄「開發用切換器」提供，對應後端三種 AdminRole（super_admin / editor / viewer）；寫入 `st.session_state["actor"]`（`{username, role, grade}`）。換真實 API 後改由認證提供，切換器移除。

---

## UI 元件清單(核心)

> **✅ = 已完成；❌ = 未實作**

| 區塊 | 實作方式 | 狀態 | 關鍵參數 / 說明 |
|---|---|---|---|
| 頁首標題 | `st.title("資料管理")` | ✅ | — |
| 分頁容器 | `st.tabs(["列表", "新增", "匯入"])` | ✅ | 包裹三個分頁內容 |
| 工具列：分類 | `st.selectbox("分類", ...)` | ✅ | 即時觸發；`key="dm_category"` |
| 工具列：排序 | `st.selectbox("排序", ...)` | ✅ | 即時觸發；`key="dm_sort"`；10 個選項（含 ID ↑/↓） |
| 工具列：每頁筆數 | `st.selectbox("每頁筆數", [20,50,100])` | ✅ | 即時觸發；`key="dm_size"` |
| 工具列：關鍵字+搜尋 | `st.form("dm_filter_form")` + `text_input` + `form_submit_button` | ✅ | 僅在按「搜尋」時套用 |
| 資料列標頭 | `st.columns([1,3,1,1,1,2,2,1,1], vertical_alignment="bottom")` + `st.caption` | ✅ | ID/標題/數值/分類/創建者/建立時間/更新時間 |
| 分隔線 | `st.divider()` | ✅ | 標頭與資料列之間；padding/margin 已歸零 |
| 逐列資料 | `st.columns([1,3,1,1,1,2,2,1,1])` + `st.write` | ✅ | 時間格式 `%Y-%m-%d %H:%M` |
| 逐列動作 | `col_edit.button` / `col_del.button` | ✅ | `can_edit(record, actor)` 控制 `disabled`；觸發寫入 trigger key |
| 分頁列 | `pagination_controls(result.total, size, key_prefix="dm")` | ✅ | 放在資料列之後 |
| 空狀態 | `empty_state("目前範圍內沒有資料")` | ✅ | 取代列表 |
| 新增表單 | `st.form("dm_create", clear_on_submit=True)` | ✅ | 標題/數值/分類/備註；`form_submit_button` → `create_record` |
| 編輯彈窗 | `@st.dialog("編輯資料")` 內 `st.form("dm_edit")` | ✅ | 預填既有值；trigger key `dm_edit_id` |
| 刪除確認 | `@st.dialog("確認刪除")` | ✅ | 顯示標題摘要；確認/取消各一欄；trigger key `dm_delete_id` |
| 匯入上傳 | `st.file_uploader("選擇檔案", type=["csv","json"])` | ✅ | 單檔 |
| 匯入預覽 | `st.dataframe`（前 10 列）+ `st.caption` | ✅ | `parse_csv_bytes` / `parse_json_bytes` 解析 |
| 匯入送出 | `st.button("確認匯入", type="primary")` | ✅ | `bulk_create` → `ImportResult`；成功/部分錯誤分別提示 |
| 操作回饋 | `st.toast` / `st.error` / `st.warning` | ✅ | 各動作成功/失敗 |

---

## 分頁一:列表(讀取 / 更新入口 / 刪除入口)

### 版面

```
── 列表 ────────────────────────────────────────────────────────────────
 [分類 ▾ 全部]  [排序 ▾ ID ↑]  [每頁筆數 ▾ 20]  [關鍵字 __________][搜尋]
                                                                      ← st.columns([2,2,1,3])
────────────────────────────────────────────────────────────────────────
 ID  標題            數值   分類    創建者  建立時間          更新時間
──────────────────────────────────────────────────────────────────────
  1  溫度異常        87.20  感測器  alice  2026-07-18 10:02  2026-07-18 10:02  [編輯][刪除]
  2  …                                                                         [編輯][刪除]
  …
────────────────────────────────────────────────────────────────────────
 ‹ 上一頁    第 1 / 2 頁 · 共 40 筆    下一頁 ›        ← pagination_controls
```

欄位比例：`[1, 3, 1, 1, 1, 2, 2, 1, 1]`（標頭 `vertical_alignment="bottom"`，資料列預設）

### 元件細節

- **工具列**：四個元件排成同一列 `st.columns([2, 2, 1, 3], vertical_alignment="center")`：
  - `分類`（`cat_area`）：`st.selectbox`，改動即時重查；`"全部"` 表示不篩選
  - `排序`（`sort_area`）：`st.selectbox`，改動即時重查；選項見「排序」小節，預設 `"ID ↑"`
  - `每頁筆數`（`size_area`）：`st.selectbox([20, 50, 100])`，改動即時重查
  - `關鍵字 + 搜尋`（`form_area`）：`st.form("dm_filter_form")`；`st.text_input` + `st.form_submit_button("搜尋")`，**點搜尋才套用**

- **篩選重置頁碼**：比對 `dm_prev_filter`（`(cat_val, kw_val)` tuple），任一改變時重置 `dm_page = 1`。
  ```python
  _prev = st.session_state.get("dm_prev_filter")
  _cur  = (cat_val, kw_val)
  if _prev is not None and _prev != _cur:
      st.session_state["dm_page"] = 1
  st.session_state["dm_prev_filter"] = _cur
  ```

- **逐列動作**：每列用 `can_edit(record, actor)` 決定按鈕 `disabled`；按鈕 key 格式 `dm_edit_{id}` / `dm_delete_{id}`；點擊寫入 trigger key 並 `st.rerun()`（見下方「編輯」「刪除」小節）。

- **分頁**：`pagination_controls(result.total, size, key_prefix="dm")` 置於資料列下方。

### 排序

`st.dataframe` 的欄位點擊為**純視覺排序**，無法觸發 Python callback，因此排序改由 **selectbox** 控制：

```python
_SORT_OPTIONS = {
    "ID ↑":      "id:asc",
    "ID ↓":      "id:desc",
    "建立時間 ↓": "created_at:desc",
    "建立時間 ↑": "created_at:asc",
    "標題 ↑":    "title:asc",
    "標題 ↓":    "title:desc",
    "數值 ↑":    "value:asc",
    "數值 ↓":    "value:desc",
    "分類 ↑":    "category:asc",
    "分類 ↓":    "category:desc",
}
sort_label = st.selectbox("排序", list(_SORT_OPTIONS), key="dm_sort")
sort = _SORT_OPTIONS[sort_label]   # 傳入 list_records(sort=sort)
```

預設值（`st.session_state.setdefault("dm_sort", "ID ↑")`）對應 `DEFAULT_SORT = "id:asc"`。

### 編輯(更新)

Dialog 採 **session_state trigger pattern（一次性 pop）**：按鈕點擊將 `record.id` 寫入 `dm_edit_id` 並 `st.rerun()`；頁面頂端的 trigger 檢查在每次 rerun 最先執行，以 `pop()` 消費 key 後呼叫 dialog。`@st.dialog` 基於 `@st.fragment`，dialog 內部互動（填表、表單送出前的 rerun）走 fragment rerun，不再過 trigger check，dialog 保持開啟；**按 X 關閉**時觸發 full page rerun，key 已消費故不重開。

```python
# ── 在 module 頂層定義（非 tab 內部）────────────────────────────
@st.dialog("編輯資料")
def _edit_dialog(record_id: int) -> None:
    try:
        record = ds.get_record(record_id)
    except RecordNotFound:
        st.warning("資料不存在或已被移除")
        if st.button("關閉", key="dm_edit_close"):
            st.session_state.pop("dm_edit_id", None)  # 已被 trigger pop()，safe no-op
            st.rerun()
        return
    except Exception as exc:          # ApiError / PermissionDenied 等（api 模式）
        render_error(exc)
        if st.button("關閉", key="dm_edit_close"):
            st.session_state.pop("dm_edit_id", None)
            st.rerun()
        return

    with st.form("dm_edit"):
        title    = st.text_input("標題", value=record.title,   key="dm_edit_title")
        value    = st.number_input("數值", value=record.value, format="%.2f", key="dm_edit_value")
        category = st.selectbox("分類", CATEGORIES,
                                index=CATEGORIES.index(record.category), key="dm_edit_category")
        note     = st.text_area("備註", value=record.note,     key="dm_edit_note")
        submitted = st.form_submit_button("更新")

    if submitted:
        try:
            ds.update_record(record_id,
                             {"title": title, "value": value,
                              "category": category, "note": note},
                             actor)
            st.session_state.pop("dm_edit_id", None)  # 已被 trigger pop()，safe no-op
            st.toast("已更新")
            st.rerun()
        except Exception as exc:
            render_error(exc)   # ValidationError / ApiError 等一律依 error-handling §3

# ── 頁面頂端 trigger 檢查（一次性 pop）────────────────────────────
if "dm_edit_id" in st.session_state:
    _edit_dialog(st.session_state.pop("dm_edit_id"))

# ── 在列表迴圈中寫入 trigger ──────────────────────────────────────
if col_edit.button("編輯", key=f"dm_edit_{record.id}", disabled=not editable):
    st.session_state["dm_edit_id"] = record.id
    st.rerun()
```

> `st.form` widget key 加上 `dm_edit_` 前綴（如 `dm_edit_title`），避免與新增表單的 key 衝突。

### 刪除

```python
# ── 在 module 頂層定義 ───────────────────────────────────────────
@st.dialog("確認刪除")
def _delete_dialog(record_id: int) -> None:
    try:
        record = ds.get_record(record_id)
    except RecordNotFound:
        st.warning("資料不存在或已被移除")
        if st.button("關閉", key="dm_delete_close"):
            st.session_state.pop("dm_delete_id", None)  # 已被 trigger pop()，safe no-op
            st.rerun()
        return
    except Exception as exc:          # ApiError / PermissionDenied 等（api 模式）
        render_error(exc)
        if st.button("關閉", key="dm_delete_close"):
            st.session_state.pop("dm_delete_id", None)
            st.rerun()
        return

    st.write(f"確定刪除「**{record.title}**」？此操作無法復原。")
    col_confirm, col_cancel = st.columns(2)
    if col_confirm.button("確認刪除", type="primary", use_container_width=True):
        try:
            ds.delete_record(record_id, actor)
            st.session_state.pop("dm_delete_id", None)  # 已被 trigger pop()，safe no-op
            st.toast("已刪除")
            st.rerun()
        except Exception as exc:
            render_error(exc)   # 失敗保留 dialog，可重試或取消
    if col_cancel.button("取消", use_container_width=True):
        st.session_state.pop("dm_delete_id", None)  # 已被 trigger pop()，safe no-op
        st.rerun()

# ── 頁面頂端 trigger 檢查（一次性 pop）────────────────────────────
if "dm_delete_id" in st.session_state:
    _delete_dialog(st.session_state.pop("dm_delete_id"))

# ── 在列表迴圈中寫入 trigger ──────────────────────────────────────
if col_del.button("刪除", key=f"dm_delete_{record.id}", disabled=not editable):
    st.session_state["dm_delete_id"] = record.id
    st.rerun()
```

> **刪除同樣要 try/except → `render_error`**：前端雖已依 `can_edit()` 停用按鈕，但 api 模式下仍可能拋 `ApiError`（逾時 / 5xx）或後端拒絕的 `PermissionDenied`。Streamlit **沒有全域錯誤邊界**，未攔截的例外會直接變成 traceback 畫面，故一律在呼叫點以 `render_error` 收斂。

---

## 分頁二:新增(建立)

```
── 新增 ──────────────────────────────────────────────────────
 標題    [________________________]                           ← st.text_input(必填)
 數值    [__________]     分類 [▾ 感測器]                       ← st.number_input(float) + st.selectbox
 備註    [________________________]  (可選)                    ← st.text_area(可選)
                                             [ 送出 ]          ← st.form_submit_button
```

- 以 `st.form("dm_create", clear_on_submit=True)` 包裹，避免逐欄 rerun。
- 欄位（對應 `Record`，選項直接用 `CATEGORIES`）：
  - 標題：`st.text_input("標題")`（必填非空）
  - 數值：`st.number_input("數值", format="%.2f")`（float）
  - 分類：`st.selectbox("分類", CATEGORIES)`
  - 備註：`st.text_area("備註")`（可選）
- **`id` / `created_by` / 時間戳由來源端自動帶入**；`actor = state.get_actor()` 傳入 `create_record`。
- 送出前前端驗證（標題非空）→ `st.error` 不送；來源端 `ValidationError` → `st.error`。
- 成功 → `st.toast("已新增")` + 清空表單（`clear_on_submit=True` 自動清）。

---

## 分頁三:匯入(批量建立)

```
── 匯入 ──────────────────────────────────────────────────────
 [ ⬆ 選擇檔案（CSV / JSON）]                                    ← st.file_uploader
──────────────────────────────────────────────────────────────
 預覽：共 N 列
 ┌────────────────────────────────────────────┐
 │ title   value   category   note            │  ← st.dataframe（前 10 列）
 │ …                                            │
 └────────────────────────────────────────────┘
 （僅顯示前 10 列）                              ← 超過 10 列時顯示
                                   [ 確認匯入 ]  ← st.button(type="primary")
```

頁面頂端顯示兩行說明文案：

```python
st.markdown("支援 **CSV**（含表頭）或 **JSON**（物件陣列），單檔最多 1000 列。")
st.markdown("必填欄位：`title`、`value`、`category`（需為感測器/系統/應用/網路之一）；選填：`note`。")
```

**匯入執行（trigger + flash pattern）**：

「確認匯入」按下後不直接呼叫 `bulk_create`，而是走與 dialog 相同的 **session trigger
pattern**（`dm_import_rows`），理由有三：

1. **錯誤處理**：`bulk_create` 在 api 模式可能拋 `ApiError` / `PermissionDenied` /
   `ValidationError`（>1000 列 422），trigger 區塊以 `render_error` 收斂，失敗不 rerun、
   保留頁框可重試。
2. **成功訊息不被 rerun 沖掉**：成功後需 `st.rerun()` 刷新列表，但直接
   `st.success(...) → st.rerun()` 會讓訊息一閃即逝。改存 `dm_import_result`（flash），
   rerun 後由分頁頂端 `pop()` 顯示。
3. **可測試性**：AppTest 不支援 `file_uploader`，測試可直接注入
   `session_state["dm_import_rows"]` 驅動完整匯入路徑。

```python
with import_tab:
    # flash：上一輪匯入結果（成功 rerun 刷新列表後，訊息仍要顯示）
    if "dm_import_result" in st.session_state:
        level, msg, detail = summarize_import(st.session_state.pop("dm_import_result"))
        {"success": st.success, "warning": st.warning}[level](msg)
        if detail:
            st.caption(detail)

    # trigger：確認匯入按下後由此執行
    if "dm_import_rows" in st.session_state:
        rows = st.session_state.pop("dm_import_rows")
        try:
            st.session_state["dm_import_result"] = ds.bulk_create(rows, actor)
            st.rerun()   # 刷新列表；結果訊息由上方 flash 區塊顯示
        except Exception as exc:
            render_error(exc)   # st.error（附 request_id），保留頁框可重試

    uploaded = st.file_uploader("選擇檔案", type=["csv", "json"], key="dm_import_file")
    if uploaded is not None:
        content = uploaded.read()
        if uploaded.name.endswith(".json"):
            rows, parse_err = parse_json_bytes(content)
        else:
            rows, parse_err = parse_csv_bytes(content)

        if parse_err:
            st.error(parse_err)
        else:
            st.caption(f"預覽：共 {len(rows)} 列")
            if rows:
                st.dataframe(pd.DataFrame(rows[:10]), hide_index=True, use_container_width=True)
                if len(rows) > 10:
                    st.caption("（僅顯示前 10 列）")
                if st.button("確認匯入", type="primary", key="dm_import_confirm",
                             disabled=not writable):
                    st.session_state["dm_import_rows"] = rows
                    st.rerun()
```

**結果訊息**（`lib/import_utils.summarize_import`，純函式）：

| 輸入 | 回傳 `(level, message, detail)` |
|---|---|
| `errors == []` | `("success", "匯入完成：成功 N 筆。", None)` |
| 有錯誤列 | `("warning", "匯入完成：成功 N 筆，錯誤 M 筆（錯誤列未建立）。", "錯誤列：3, 5…")`（列號 1-based，只列前 5 列，超過加 `…`） |

必填欄位：`title`（非空字串）、`value`（可轉 float）、`category`（∈ `CATEGORIES`）；選填：`note`。單檔上限 1000 列，超限拒絕整批。

---

## 權限規則

| 動作 | 允許者 | 前端呈現 |
|---|---|---|
| 讀取 | 所有登入者（任何 grade） | 一律可用 |
| 建立 / 批量匯入 | `grade > AdminRole.VIEWER`（>0；editor/super_admin/root） | viewer（0）→ 送出按鈕 `disabled`（唯讀） |
| 更新 / 刪除 | `grade > AdminRole.VIEWER` | 無權限 → 按鈕 `disabled=True`（停用不隱藏） |

- 權限判斷用純函式 `can_edit(record, actor)`，其 admin 分支**委派 `can_write(actor)`**（`grade > AdminRole.VIEWER` 的唯一真相；系統管理頁共用 `can_write`）：
  - `actor.role == "admin"` → `can_write(actor)`：`grade == 0`（viewer）→ **False**（唯讀）；`grade > 0` → **True**（可編輯任何記錄）
  - `actor.role == "user"` → `record.created_by == actor.username`（**latent 分支**：本部署無 user role，不會觸發）
- 新增 / 匯入按鈕的 `disabled` 直接用 `can_write(actor)`（無 record 可傳）。
- **後端 API 亦強制驗證**，前端控制僅為體驗。
- `actor` 取自 `st.session_state["actor"]`：mock 由開發切換器提供，正式由認證（見 [ADR 0003](../decisions/0003-auth-via-bff-token-exchange.md)）提供。

---

## 資料模型

records 由**來源端**擁有(mock 記憶體 / 日後後端 API),前端經 `DataSource` 介面存取。欄位與型別詳見[資料來源規格](../data-source.md#資料契約型別定義):

`id:int, title:str, value:float, category, created_by, created_at, updated_at, note:str="", deleted_at?`(軟刪除)

---

## 狀態與錯誤處理

層級 / 文案 / `request_id` 依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威);本頁映射如下:

| 情境 | 呈現 |
|---|---|
| 載入中 | `st.spinner` / 表格骨架 |
| 查無資料 | `empty_state("目前範圍內沒有資料")`（`st.info`），取代列表 |
| 建立/更新/刪除成功 | `st.toast` + `st.rerun()` 刷新 |
| 匯入成功 / 部分錯誤 | flash（`dm_import_result`）→ rerun 後 `st.success` / `st.warning` + `st.caption` 錯誤列（`summarize_import`） |
| **任一 `ds.*` 失敗（逾時 / 5xx / 403 / 422 / 404）** | 呼叫點 `except Exception → render_error(exc)`——層級 / 文案 / request_id 依 error-handling §3；頁面級保留頁框、dialog 級保留 dialog，均可重試。**Streamlit 無全域錯誤邊界，禁止讓例外往上冒。** |
| 找不到資料（dialog 載入） | `RecordNotFound`(對應 404)→ dialog 內 `st.warning`「資料不存在或已被移除」+ 關閉按鈕（特化分支，先於泛用分支） |
| 建立/更新欄位不合法 | `ValidationError`(對應 422)→ `render_error` → `st.error`「欄位不合法:…」留在 form 內 |
| 匯入格式錯誤（解析階段） | `parse_*_bytes` 回傳 error_msg → `st.error`，不進入 `bulk_create` |
| 未登入（`NotAuthenticated`） | `render_error` re-raise → app.py 清 session 導向登入 |

---

## 樣式對照(設計 Token)

| 用途 | Token | 說明 |
|---|---|---|
| 主要按鈕 / 送出 | primary `#2563eb` | 新增、確認匯入 |
| 刪除 / 錯誤列 | danger `#dc2626` | 刪除確認 |
| 成功提示 | success `#16a34a` | toast / success |
| 區塊底色 | secondaryBackground `#f1f5f9` | 卡片 / 指標卡 |

- 顏色一律走主題 token，不散寫魔術數字。
- `st.divider()` 的上下 padding 與 margin 已在 `styles/main.css` 歸零。

---

## 效能與依賴 / 備註

- **分頁 / 篩選 / 排序在來源端**：頁面只傳 `page` / `size` / `category` / `keyword` / `sort` 給 `DataSource`，mock 於記憶體處理、日後由後端 API 處理，避免全量載入前端。
- 讀取類查詢可用 `st.cache_data` 設短 TTL（mock 階段可略）；寫入後主動清快取或 `st.rerun()`。
- 大量匯入分批送出，避免單次請求過大；mock 上限單檔 1000 列。

---

## 可測試性(對齊 TDD)

- 純邏輯抽到 `lib/`（不依賴 Streamlit）：`can_edit(record, actor)`、`MockDataSource` 的分頁/篩選/排序/CRUD、匯入解析與驗證 → `tests/unit/`。
- 頁面行為以 `AppTest` 覆蓋：切換使用者後按鈕停用、分頁切換、匯入錯誤列標示、送出後刷新 → `tests/app/`。
- 完整行為切分與 RED 順序見[資料來源規格「對齊 TDD 的落地順序」](../data-source.md#對齊-tdd-的落地順序)。

### 本頁 TDD 落地順序（承接 data-source.md 第 8 步）

> ✅ = 已有測試且通過

| # | 行為 | 測試位置 | 狀態 |
|---|---|---|---|
| 8-1 | 切換 Actor 後按鈕停用/啟用（含 Viewer 全停用） | `tests/app/test_data_management.py` | ✅ 完成 |
| 8-2 | 篩選條件傳入 `list_records`（分類篩選後列表正確） | `tests/app/test_data_management.py` | ✅ 完成 |
| 8-3 | 分頁切換（下一頁/上一頁更新列表） | `tests/app/test_data_management.py` | ✅ 完成 |
| 8-4 | 新增表單送出後列表刷新、筆數+1 | `tests/app/test_data_management.py` | ✅ 完成 |
| 8-5 | 編輯彈窗開啟、修改、更新後列表刷新 | `tests/app/test_data_management.py` | ✅ 完成 |
| 8-5r | **[Regression]** 編輯 dialog 按 X 關閉後再次 rerun 不重開 | `tests/app/test_data_management.py` | ✅ 完成 |
| 8-6 | 刪除確認彈窗、確認後列表筆數-1 | `tests/app/test_data_management.py` | ✅ 完成 |
| 8-7 | 匯入分頁渲染（AppTest 不支援 file_uploader，頁面不 crash） | `tests/app/test_data_management.py` | ✅ 完成 |
| 8-8 | 匯入解析：CSV/JSON 格式、超限拒絕、缺欄拒絕 | `tests/unit/test_import_utils.py` | ✅ 完成 |
| 8-9 | 排序選單存在且切換後順序改變 | `tests/app/test_data_management.py` | ✅ 完成 |
