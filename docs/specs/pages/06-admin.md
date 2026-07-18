# 頁面規格:系統管理

- 頁面編號:6
- 對應模組:模組 5 系統管理
- 存取權限:**所有登入者可讀**（本系統為 admin-only,三種 grade `super_admin` / `editor` / `viewer` 皆可進本頁）；**寫入操作限 `grade != "viewer"`**（`super_admin` / `editor` 可寫,`viewer` 唯讀）。後端 API 亦強制驗證。存取軸的權威定義見[前端頁面結構 §存取控制](../frontend-pages.md#存取控制本節為存取軸的單一真相)。
- 導覽:因所有登入者皆為 admin role,`build_pages` 對每個人都註冊此頁;差異在**寫入按鈕依 `can_write(actor)` 停用**,非頁面層 gate——見[應用骨架 §5](../app-skeleton.md#5-導覽與頁面註冊build_pages)
- 相關:[UI Helper 規格](../ui.md)、[錯誤處理規格](../error-handling.md)

## 目的

提供 Admin 管理使用者、權限、系統日誌與資料庫狀態,並查詢即時資料的歷史紀錄。

## 版面

以 `st.tabs` 分為四個分頁:使用者 / 權限 / 日誌 / DB 狀態。

## UI 版面規劃

寬版,`st.tabs(["使用者", "權限", "日誌", "DB 狀態"])`。頁面對所有登入者開放;進入時算出 `writable = can_write(actor)`,`viewer`(`writable=False`)所有寫入按鈕停用。

```
[ 使用者 ] [ 權限 ] [ 日誌 ] [ DB 狀態 ]                 ← st.tabs
── 使用者 ──────────────────────────────────────────────
 搜尋[____] 角色[▾] 狀態[▾]                              ← filter_bar(key_prefix="admin_user")
 帳號  Email  角色  建立時間  狀態   [停用/啟用]          ← st.dataframe/逐列

── 權限 ────────────────────────────────────────────────
 使用者[▾]  grade super_admin/editor/viewer  [ 變更 ]  → st.dialog 二次確認 + 寫日誌（viewer 停用）

── 日誌 ────────────────────────────────────────────────
 時間範圍  使用者[▾]  等級[▾]  ← filter_bar(key_prefix="admin_log")
 時間  使用者  動作  結果 (等級著色)   ← st.dataframe + pagination_controls

── DB 狀態 ──────────────────────────────────────────────
 ┌─────────┬─────────┬─────────┐
 │ 連線狀態 │ 各表列數 │ DB 大小  │   ← metric_cards(3 個 Metric)
 └─────────┴─────────┴─────────┘
 即時資料歷史查詢:時間範圍 → st.dataframe
```

| 分頁 | 主要元件 | 備註 |
|---|---|---|
| 使用者 | `filter_bar(key_prefix="admin_user")` + `st.dataframe` + 停用/啟用 button | 敏感操作寫日誌 |
| 權限 | `st.selectbox` + `st.dialog` 確認 | 變更 grade;不可降為最後一位 super_admin;viewer 停用 |
| 日誌 | `filter_bar(key_prefix="admin_log")` + `st.dataframe` + `pagination_controls` | 等級以狀態色著色 |
| DB 狀態 | `metric_cards()` + `st.dataframe` | 唯讀 |

---

## 功能細節

### 存取與寫入 gate

本頁**不做頁面層 role gate**——本系統只有 admin role 進得來,`if actor.role != "admin"` 恆為 false,是無效 gate。存取差異一律由 `grade` 決定:三種 grade 皆可讀,寫入限 `grade != "viewer"`。頁面進入時算一次 `writable`,供所有寫入按鈕共用:

```python
from lib.state import get_actor
from lib.models import can_write

actor = get_actor()
writable = actor is not None and can_write(actor)   # super_admin / editor → True；viewer → False
```

- `writable=False`(viewer):停用「停用/啟用帳號」「變更角色」等按鈕(`disabled=not writable`),不隱藏,呈現唯讀。
- **深度防禦**:前端停用僅為體驗,後端管理 API 一律再驗 grade;`viewer` 即使繞過前端,後端回 `403 PermissionDenied` → `st.error`。
- `role == "user"` 分支(非本部署身分)在 `can_write` 一律回 `False`,作為 latent 防線。

### 使用者分頁

以 `filter_bar` 管理搜尋/篩選:

```python
from lib.ui import filter_bar

fp = filter_bar(
    categories=["全部", "admin", "user"],   # 角色篩選
    key_prefix="admin_user",
    show_date=False,
    show_keyword=True,   # 帳號/Email 搜尋
)
```

- `st.dataframe` 列出所有使用者(帳號、Email、角色 / grade、建立時間、狀態)——**viewer 亦可讀此列表**。
- 每列「停用」/「啟用」按鈕:`disabled=not writable`(viewer 停用);可寫者點擊 → `@st.dialog` 二次確認 → 呼叫 `PATCH /admin/users/{id}` → `st.toast` 回饋 + 刷新。
- 敏感操作後端寫稽核日誌,前端不重複記。
- API endpoint(placeholder):`GET /admin/users`。

### 權限分頁

```python
target_user = st.selectbox("選擇使用者", user_list)
new_grade = st.radio("新權限", ["super_admin", "editor", "viewer"])
if st.button("變更權限", disabled=not writable):   # viewer 停用
    # 開 st.dialog 二次確認
    ...
```

- 變更的是使用者的 **grade**(`super_admin` / `editor` / `viewer`);`viewer` 無此按鈕(唯讀)。
- **不可將自己降為最後一個 super_admin**:後端以 `ValidationError`(422)回絕 → `st.error`「無法移除最後一位 super_admin」。
- 成功 → `st.toast` + 刷新使用者列表。
- API endpoint(placeholder):`PATCH /admin/users/{id}/role`。

### 日誌分頁

以 `filter_bar` + `pagination_controls` 管理:

```python
from lib.ui import filter_bar, pagination_controls, empty_state

fp = filter_bar(
    categories=["全部", "INFO", "WARNING", "ERROR"],
    key_prefix="admin_log",
    show_keyword=False,
)
page = pagination_controls(total=log_total, size=50, key_prefix="admin_log")
```

- `st.dataframe` 含等級著色(以 `column_config` 或 CSS 處理等級色)。
- API endpoint(placeholder):`GET /admin/logs?from=&to=&user=&level=&page=&size=`。

### DB 狀態分頁

以 `metric_cards` 呈現 3 個指標:

```python
from lib.ui import metric_cards, Metric

metric_cards([
    Metric("連線狀態", "正常" if db_ok else "異常",
           delta_color="off" if db_ok else "inverse"),
    Metric("各表列數", total_rows),
    Metric("DB 大小", f"{db_size_mb:.1f} MB"),
])
```

- 歷史查詢:`st.date_input` 選時間範圍 → `GET /admin/records/history` → `st.dataframe`。
- API endpoint(placeholder):`GET /admin/db/status`、`GET /admin/records/history`。

---

## Mock 模式行為（`DATA_SOURCE=mock`）

> **重要**:`MockDataSource` 目前**只支援 records CRUD**,不含 users / logs / db-status。本頁 mock 階段的管理資料由 `lib/system_management.py`(新增)的**靜態種子 + 純函式**提供,不呼叫網路;換 `DATA_SOURCE=api` 後才改打管理 API。此為本頁能在 mock 先行下完整呈現與測試的前提。

| 分頁 | Mock 資料來源 | Mock 寫入行為 |
|---|---|---|
| 使用者 | 首次進頁由 `seed_users()` 植入 `st.session_state["admin_users"]`;之後恆讀此 list | 停用/啟用:**就地改 `admin_users` 內對應 dict 的 `status`** + `st.toast` + `st.rerun()`;不落持久層 |
| 權限 | 同上 `admin_users` list | 變更 grade:先過 `is_last_super_admin(admin_users, target)` 擋降級最後一位 → 就地改該 dict 的 `grade`;否則 `st.error` |
| 日誌 | `lib/system_management.py::seed_logs()` 靜態假日誌(含 INFO/WARNING/ERROR) | 唯讀,無寫入 |
| DB 狀態 | `lib/system_management.py::seed_db_status()` 靜態假指標(連線正常、表列數、DB 大小) | 唯讀,無寫入 |

- **可變狀態單一真相**:mock 的使用者名單只存於 `st.session_state["admin_users"]`（見 §session_state 契約）;所有寫入就地改這個 list,`seed_users()` 只在 `setdefault` 首次植入,不在每次 rerun 重置（否則改動會被沖掉）。
- mock 模式下**不需登入 BFF** 亦可完整呈現(讀取全開);`viewer` 身分下所有寫入按鈕停用,可直接以 AppTest 驗證。
- 寫入類 API endpoint(`PATCH /admin/users/*`)在 mock 階段**不呼叫**;僅 `DATA_SOURCE=api` cycle 才接。

---

## `lib/system_management.py` 純函式契約（單一真相）

所有函式**無 Streamlit 依賴**,可直接單元測試。

| 函式 | 簽章 | 契約 |
|---|---|---|
| `color_log_level` | `(level: str) -> str` | `"ERROR"` / `"WARNING"` / `"INFO"` → 對應色彩 token(或 CSS class);未知等級回中性色。 |
| `is_last_super_admin` | `(users: List[dict], target_username: str) -> bool` | `target` 目前為 `super_admin` 且名單內 `super_admin` 僅剩此一位 → `True`(擋降級 / 停用);否則 `False`。 |
| `format_db_size` | `(size_bytes: int) -> str` | 位元組 → `"{:.1f} MB"`(或適當單位)字串;`0 → "0.0 MB"`。 |
| `seed_users` / `seed_logs` / `seed_db_status` | `() -> list` / `() -> list` / `() -> dict` | mock 靜態種子;決定性、不依賴時鐘。 |

> 寫入權限判斷用 `lib/models.py::can_write(actor)`(見 [Auth / models 契約]),本頁與資料管理**共用同一條 `grade != "viewer"`**,不在 `lib/system_management.py` 另立。

---

## 資料

- 透過後端**管理 API** 存取 users / logs / records / realtime;前端不直接連 DB。
- 敏感操作(停用帳號、角色變更)呼叫對應 API,由後端寫稽核日誌。

---

## 權限規則

- **讀取**:所有登入者(三種 grade)皆可進本頁並讀取四分頁。
- **寫入**(停用帳號、變更 grade):限 `can_write(actor)`(`grade != "viewer"`);`viewer` 一律按鈕停用 + 後端再驗(深度防禦)。
- 不可將自己降為最後一位 `super_admin`(後端 `ValidationError` 回絕,mock 由 `is_last_super_admin` 擋)。
- 角色變更、帳號停用等敏感操作由後端寫稽核日誌。

---

## session_state 契約

使用 `admin_user_` 與 `admin_log_` 前綴(見 [UI Helper §7](../ui.md#7-狀態命名規範)):

| Key | 由誰管理 | 說明 |
|---|---|---|
| `admin_user_category` | `filter_bar()` | 使用者分頁角色篩選 |
| `admin_user_keyword` | `filter_bar()` | 使用者分頁搜尋關鍵字 |
| `admin_log_category` | `filter_bar()` | 日誌分頁等級篩選 |
| `admin_log_date_from` | `filter_bar()` | 日誌分頁起始日期 |
| `admin_log_date_to` | `filter_bar()` | 日誌分頁結束日期 |
| `admin_log_page` | `pagination_controls()` | 日誌分頁當前頁碼 |
| `admin_users` | 頁面（mock 寫入層） | **mock 階段的可變使用者名單**：首次進頁 `st.session_state.setdefault("admin_users", seed_users())` 植入；停用/啟用、變更 grade 一律**就地改此 list**（單一真相），rerun 由此讀取渲染。`DATA_SOURCE=api` 時不使用（改打管理 API）。 |
| `last_request_id` | `render_error` | 管理 API 失敗時附錯誤代碼 |

---

## 狀態與錯誤處理

本頁對所有登入者開放讀取,存取差異由 grade 決定(見 §存取與寫入 gate);頁內操作失敗的呈現一律依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威):

| 情境 | 依 §3 呈現 |
|---|---|
| `viewer` 進入 | 頁面正常渲染(四分頁可讀);所有寫入按鈕 `disabled`,不出現「僅限 Admin」錯誤 |
| 敏感操作被拒(viewer 繞過前端 / 遇 403) | `PermissionDenied` → `st.error`;對已知無權的操作**預先停用按鈕** |
| 不可將自己降為最後一位 super_admin | `ValidationError`(422)→ dialog 內 `st.error`「無法移除最後一位 super_admin」;變更不生效 |
| 查詢 / 載入失敗(使用者、日誌、DB 狀態) | `ApiError` → `st.error` + 保留頁框 + 可重試(附錯誤代碼) |
| 無資料(篩選後) | `empty_state()` 取代對應 `st.dataframe` |

> 敏感操作(停用帳號、角色變更)無論成功或被拒,後端一律寫稽核日誌;前端只負責依上表呈現結果。

---

## lib/ 依賴

| 模組 | 用途 |
|---|---|
| `lib/ui.py` | `filter_bar`、`metric_cards`、`pagination_controls`、`empty_state` |
| `lib/errors.py` | `render_error` |
| `lib/state.py` | `get_actor()`（取當前 actor 判斷 `can_write`）|
| `lib/models.py` | `can_write(actor)`（寫入 gate,與資料管理共用）|
| `lib/system_management.py` | `color_log_level`、`is_last_super_admin`、`format_db_size`、mock 種子（新增）|
| `lib/api_client.py` | `DATA_SOURCE=api` 時管理 API 所有讀寫呼叫 |

---

## 可測試性 / TDD

### 純函式（`tests/unit/test_system_management.py`）

1. `color_log_level("ERROR")` — 回正確色彩 token（或 CSS class）；`"INFO"` / `"WARNING"` / 未知等級亦覆蓋。
2. `is_last_super_admin(users, target)` — target 為唯一 `super_admin` 時回 `True`；有兩位以上 `super_admin` 回 `False`；target 非 super_admin 回 `False`。
3. `format_db_size(bytes)` — 正確格式化為 MB 字串（含 `0 → "0.0 MB"`）。
4. `can_write` 分支（於 `tests/unit/test_models.py`）：`grade="viewer"` → `False`；`super_admin` / `editor` → `True`。

### 頁面行為（`tests/app/test_system_management.py`，AppTest）

5. `viewer` 進入 → 頁面含「系統管理」標題、四分頁**皆可讀**，**不**含「僅限 Admin」錯誤，且寫入按鈕 `disabled`。
6. `editor` / `super_admin` + mock → 寫入按鈕**未**停用（可寫）。
7. 任一 grade + mock → 頁面含「系統管理」標題與四分頁（使用者/權限/日誌/DB 狀態）。
8. `GET /admin/users` 失敗（api 模式）→ 含 `st.error` + 「錯誤代碼」。
9. 篩選後無資料 → 含 `st.info` 空狀態。

> 依 CLAUDE.md，逐一先寫失敗測試 → 最小實作 → 綠燈重構。存取軸為 grade（非 role）；先做 `lib/models.py::can_write` 與 `lib/system_management.py` 純函式（unit 1–4），再做頁面（AppTest 5–9）。

---

## 依賴 / 備註

- 敏感操作建議全部留稽核紀錄（後端責任）。
- Admin API endpoints 均為 placeholder，待後端對齊後填入。
