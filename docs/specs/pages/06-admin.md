# 頁面規格:系統管理

- 頁面編號:6
- 對應模組:模組 5 系統管理
- 存取權限:**僅 `grade >= AdminRole.SUPER_ADMIN`（≥100，含 ROOT=999）**（`editor` / `viewer` 不可見；由 `build_pages(actor)` 動態不註冊，比隱藏連結更安全）。存取軸的權威定義見[前端頁面結構 §存取控制](../frontend-pages.md#存取控制本節為存取軸的單一真相)。
- 導覽:`build_pages(actor)` 僅在 `actor.grade >= AdminRole.SUPER_ADMIN` 時追加此頁——見[應用骨架 §5](../app-skeleton.md#5-導覽與頁面註冊build_pages)
- 相關:[UI Helper 規格](../ui.md)、[錯誤處理規格](../error-handling.md)

## 目的

提供 Admin 查閱系統日誌與資料庫狀態，以及管理員帳號的完整生命週期管理（新增／更新／升降權／封存／刪除）。

## 版面

以 `st.tabs` 分為三個分頁:日誌 / DB 狀態 / 管理員管理。

## UI 版面規劃

寬版,`st.tabs(["日誌", "DB 狀態", "管理員管理"])`。前兩分頁唯讀，管理員管理分頁有寫入操作。

```
[ 日誌 ] [ DB 狀態 ] [ 管理員管理 ]                        ← st.tabs

── 日誌 ────────────────────────────────────────────────
 時間範圍  使用者[▾]  等級[▾]  ← filter_bar(key_prefix="admin_log")
 時間  使用者  動作  結果 (等級著色)   ← st.dataframe + pagination_controls

── DB 狀態 ──────────────────────────────────────────────
 ┌─────────┬─────────┬─────────┐
 │ 連線狀態 │ 各表列數 │ DB 大小  │   ← metric_cards(3 個 Metric)
 └─────────┴─────────┴─────────┘
 即時資料歷史查詢:時間範圍 → st.dataframe

── 管理員管理 ─────────────────────────────────────────────
 狀態篩選[active▾]  [+ 新增管理員]        ← 右上角建立按鈕
 帳號  顯示名稱  權限等級  狀態  操作
 alice  Alice Wu   超管 🔒  active  [改名] [──] [──]    ← root：操作全停用
 bob    Bob Chen   編輯者    active  [改名] [升降權] [封存] [刪除]
 carol  Carol Lin  檢視者    archived  [改名] [升降權] [解封存] [刪除]
                                               ← st.dataframe + 操作按鈕列
```

| 分頁 | 主要元件 | 備註 |
|---|---|---|
| 日誌 | `filter_bar(key_prefix="admin_log")` + `st.dataframe` + `pagination_controls` | 等級以狀態色著色 |
| DB 狀態 | `metric_cards()` + `st.dataframe` | 唯讀 |
| 管理員管理 | `st.selectbox`（狀態篩選）+ `st.dataframe` + 操作按鈕 | root（is_protected=True）操作全停用 |

---

## 功能細節

### 管理員管理分頁

#### 列表與篩選

```python
from lib.models import AdminRole
from lib.admin_management import grade_label, admin_status_options

status_filter = st.selectbox("狀態", ["active", "archived", "deleted", "all"], key="admins_status")
# GET /admin/admins?status={status_filter}&limit=50&offset=...
# 回 AdminListResponse { items: [AdminSummary], total, limit, offset }
```

`AdminSummary` 欄位用途：

| 欄位 | UI 用途 |
|---|---|
| `username` | 顯示帳號 |
| `name` | 顯示名稱（可編輯） |
| `admin_role` | 整數→ `grade_label()` 轉文字（0→檢視者/50→編輯者/100→超管/999→根管理員） |
| `is_protected` | `True` → 行尾標 🔒，**所有操作按鈕停用**（tooltip「Root 不可移除」） |
| `is_active` | 顯示狀態徽章（active/archived/deleted） |
| `archived_by_username` / `deleted_by_username` | 顯示「由 xxx 操作」提示 |

#### 建立管理員

- `[+ 新增管理員]` 按鈕 → `st.form(key="create_admin_form")`，含：`username`、`顯示名稱`、`密碼`（`type="password"`）、`權限等級`（`selectbox`：檢視者/編輯者/超管）。
- 送出：`POST /admin/admins` → 201 → 重新整理列表；409（帳號重複）→ `st.error`；400（格式錯誤）→ `st.error`。

#### 改名（`PATCH /admin/admins/{id}`）

- 每行「改名」按鈕 → `st.form(key=f"rename_{id}")` + `st.text_input`。
- 回 200 `AdminResponse` → 刷新列表；`is_protected` admin 的按鈕不停用（root 可自改名）。

#### 升降權（`PUT /admin/admins/{id}/role`）

- 「升降權」按鈕 → `st.selectbox` 選新等級 → `PUT /admin/admins/{id}/role`。
- `is_protected` admin（root）→ 按鈕停用（tooltip「Root 不可降級」）。
- 422 → `st.warning`（例：「Super Admin 須先降級才能封存」）。

#### 封存 / 解封存 / 刪除 / 復原

| 動作 | 端點 | 前提 |
|---|---|---|
| 封存 | `POST /admin/admins/{id}/archive` | `is_active=True`、`admin_role < SUPER_ADMIN`（已降級）、非 `is_protected` |
| 解封存 | `POST /admin/admins/{id}/unarchive` | `is_active=False`（archived）|
| 刪除 | `DELETE /admin/admins/{id}` | 同封存限制 |
| 復原 | `POST /admin/admins/{id}/restore` | `deleted_at` 有值 |

- 所有生命週期操作回 200 `AdminSummary` → 刷新列表。
- 422（超管未降級 / 操作自己）→ `st.warning`；is_protected admin → 按鈕停用。

#### 自己改密碼（另立入口）

- 於頁眉提供「修改密碼」連結，呼叫 `POST /admin/me/password`（需舊密碼）；成功後登出重登（204→清 session）。
- **不提供**「重設他人密碼」操作，無此按鈕。

---

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

> **重要**:`MockDataSource` 目前**只支援 records CRUD**,不含 logs / db-status / admin 管理。本頁 mock 階段的管理資料由 `lib/system_management.py` 及 `lib/admin_management.py` 的**靜態種子 + 純函式**提供,不呼叫網路;換 `DATA_SOURCE=api` 後才改打管理 API。

| 分頁 | Mock 資料來源 |
|---|---|
| 日誌 | `seed_logs()` 靜態假日誌（含 INFO/WARNING/ERROR） |
| DB 狀態 | `seed_db_status()` 靜態假指標（連線正常、表列數、DB 大小） |
| 管理員管理 | `seed_admins()` 靜態假管理員清單（含多種 grade 與 is_protected=True 的 root）|

- 日誌 / DB 狀態分頁唯讀，無寫入操作，無可變 session_state。
- 管理員管理分頁的寫入操作（建立 / 封存 / 刪除）在 mock 模式下顯示按鈕但操作後**只顯示 `st.info("mock 模式，操作不持久")`**，不實際修改種子。
- mock 模式下**不需登入 BFF** 亦可完整呈現；可直接以 AppTest 驗證。

---

## `lib/system_management.py` 純函式契約（單一真相）

所有函式**無 Streamlit 依賴**,可直接單元測試。

| 函式 | 簽章 | 契約 |
|---|---|---|
| `color_log_level` | `(level: str) -> str` | `"ERROR"` / `"WARNING"` / `"INFO"` → 對應色彩 token(或 CSS class);未知等級回中性色。 |
| `format_db_size` | `(size_bytes: int) -> str` | 位元組 → `"{:.1f} MB"`(或適當單位)字串;`0 → "0.0 MB"`。 |
| `seed_logs` / `seed_db_status` | `() -> list` / `() -> dict` | mock 靜態種子;決定性、不依賴時鐘。 |

## `lib/admin_management.py` 純函式契約（單一真相）

所有函式**無 Streamlit 依賴**,可直接單元測試。

| 函式 | 簽章 | 契約 |
|---|---|---|
| `grade_label` | `(grade: int) -> str` | `0→"檢視者"`, `50→"編輯者"`, `100→"超管"`, `999→"根管理員"`;未知值回 `str(grade)`。 |
| `can_manage_admin` | `(actor: Actor, target_is_protected: bool) -> bool` | `is_protected=True` → `False`（root 不可被一般操作管理）；否則 `actor.grade >= AdminRole.SUPER_ADMIN` → `True`。 |
| `seed_admins` | `() -> list[dict]` | mock 靜態種子：至少含 root（is_protected=True, grade=999）、super_admin、editor、viewer 各一；決定性、不依賴時鐘。 |

---

## 資料

- 透過後端**管理 API** 存取 logs / db-status / admin CRUD；前端不直接連 DB。
- 日誌 / DB 狀態分頁唯讀；管理員管理分頁有寫入操作（需 grade ≥ SUPER_ADMIN，與頁面進入條件一致）。

---

## 權限規則

- **頁面進入**：`grade >= AdminRole.SUPER_ADMIN`（≥100）才可見此頁（由 `build_pages` 動態不註冊）。
- **日誌 / DB 狀態分頁**：所有進入者皆可讀取，無寫入。
- **管理員管理分頁**：進入者皆可執行所有操作（listing、CRUD）；但 `is_protected=True`（root）的管理員**所有操作按鈕停用**（前端守衛）；後端亦返回 422（雙重保護）。

---

## session_state 契約

使用頁面前綴(見 [UI Helper §7](../ui.md#7-狀態命名規範)):

| Key | 前綴 | 由誰管理 | 說明 |
|---|---|---|---|
| `admin_log_category` | `admin_log_` | `filter_bar()` | 日誌分頁等級篩選 |
| `admin_log_date_from` | `admin_log_` | `filter_bar()` | 日誌分頁起始日期 |
| `admin_log_date_to` | `admin_log_` | `filter_bar()` | 日誌分頁結束日期 |
| `admin_log_page` | `admin_log_` | `pagination_controls()` | 日誌分頁當前頁碼 |
| `admins_status` | `admins_` | `st.selectbox` | 管理員管理分頁狀態篩選（active/archived/deleted/all） |
| `admins_page` | `admins_` | `pagination_controls()` | 管理員管理分頁當前頁碼 |
| `last_request_id` | — | `render_error` | 管理 API 失敗時附錯誤代碼 |

---

## 狀態與錯誤處理

頁內所有操作失敗的呈現一律依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威):

| 情境 | 依 §3 呈現 |
|---|---|
| grade≥100 進入 | 頁面正常渲染（三分頁皆可用），不出現「僅限 Admin」錯誤 |
| 查詢 / 載入失敗（日誌、DB 狀態、管理員列表） | `ApiError` → `st.error` + 保留頁框 + 可重試（附錯誤代碼） |
| 無資料（篩選後） | `empty_state()` 取代對應 `st.dataframe` |
| 建立 / 封存 / 刪除失敗（409/422） | `st.error` / `st.warning` 顯示後端訊息；保留表單或列表 |
| is_protected admin 操作按鈕 | 前端停用（disabled），tooltip「Root 不可移除」；不發送 API |

---

## lib/ 依賴

| 模組 | 用途 |
|---|---|
| `lib/ui.py` | `filter_bar`、`metric_cards`、`pagination_controls`、`empty_state` |
| `lib/system_management.py` | `color_log_level`、`format_db_size`、`seed_logs`、`seed_db_status` |
| `lib/admin_management.py` | `grade_label`、`can_manage_admin`、`seed_admins` |
| `lib/models.py` | `AdminRole` 常數（grade 數值比較） |
| `lib/errors.py` | `render_error`（接後端後才引入） |
| `lib/api_client.py` | 管理 API 呼叫（接後端後才引入） |

---

## 可測試性 / TDD

### 純函式（`tests/unit/test_system_management.py`）

1. `color_log_level("ERROR")` — 回正確色彩 token（或 CSS class）；`"INFO"` / `"WARNING"` / 未知等級亦覆蓋。
2. `format_db_size(bytes)` — 正確格式化為 MB 字串（含 `0 → "0.0 MB"`）。

### 純函式（`tests/unit/test_admin_management.py`）

3. `grade_label(0)→"檢視者"`、`grade_label(50)→"編輯者"`、`grade_label(100)→"超管"`、`grade_label(999)→"根管理員"`；未知值回 `str(grade)`。
4. `can_manage_admin(actor_super_admin, is_protected=False) → True`。
5. `can_manage_admin(actor_super_admin, is_protected=True) → False`（root 不可管理）。
6. `seed_admins()` 包含至少一筆 `is_protected=True`（root）與三種不同 grade；決定性（多次呼叫相同）。

### 頁面行為（`tests/app/test_system_management.py`，AppTest）

7. super_admin + mock → 頁面含「系統管理」標題與**三個**分頁（日誌/DB 狀態/管理員管理），**不**含「使用者」或「權限」分頁。
8. DB 狀態分頁含 `metric_cards`（連線狀態、各表列數、DB 大小）。
9. 日誌分頁渲染種子日誌（無 exception）。
10. 管理員管理分頁渲染種子 admin 列表（無 exception）；root（is_protected=True）的封存 / 刪除按鈕為 disabled。
11. 日誌分頁日期篩選型別安全：注入 `admin_log_date_range=(date(2025,1,1), date(2025,12,31))` → 無 exception；種子日誌時間均在 2024 年，故 2025 年範圍無符合記錄 → `empty_state`（「無符合條件的日誌」）。（回歸：`date` 物件與字串混合 `<=` 比較已修正為 `str(date)` 做字典序比對。）

> 依 CLAUDE.md，逐一先寫失敗測試 → 最小實作 → 綠燈重構。先做 `lib/system_management.py` 純函式（unit 1–2）→ `lib/admin_management.py` 純函式（unit 3–6）→ 頁面（AppTest 7–11）。

---

## API Endpoints（對應後端 `/admin/admins/...`）

| 操作 | 方法 & 路徑 | 請求 / 回應 |
|---|---|---|
| 列表 | `GET /admin/admins?status=&limit=&offset=` | `AdminListResponse` |
| 建立 | `POST /admin/admins` | body: username/name/password/admin_role → 201 `AdminResponse` |
| 改名 | `PATCH /admin/admins/{id}` | body: name → 200 `AdminResponse` |
| 升降權 | `PUT /admin/admins/{id}/role` | body: admin_role(int) → 200 `AdminResponse` |
| 封存 | `POST /admin/admins/{id}/archive` | 200 `AdminSummary` |
| 解封存 | `POST /admin/admins/{id}/unarchive` | 200 `AdminSummary` |
| 刪除 | `DELETE /admin/admins/{id}` | 200 `AdminSummary` |
| 復原 | `POST /admin/admins/{id}/restore` | 200 `AdminSummary` |
| 改自己密碼 | `POST /admin/me/password` | body: current_password/new_password → 204 |

> `AdminSummary.is_protected`（bool）供前端決定哪些按鈕停用；`admin_role` 為 **int**（`AdminRole` 數值）。

## 依賴 / 備註

- 敏感操作（封存 / 刪除）建議全部留稽核紀錄（後端責任，`archived_by` / `deleted_by` 欄位）。
- `admin_role` 在 API 請求與回應均為 **int**（0/50/100/999）；`grade_label()` 負責轉為顯示文字。
