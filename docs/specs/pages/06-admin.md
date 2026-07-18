# 頁面規格:系統管理

- 頁面編號:6
- 對應模組:模組 5 系統管理
- 存取權限:**僅 Admin**（非 Admin 動態不註冊此頁面；後端 API 亦強制驗證）
- 導覽:非 Admin 不註冊此頁面(而非僅隱藏連結)——見[應用骨架 §5](../app-skeleton.md#5-導覽與頁面註冊build_pages)
- 相關:[UI Helper 規格](../ui.md)、[錯誤處理規格](../error-handling.md)

## 目的

提供 Admin 管理使用者、權限、系統日誌與資料庫狀態,並查詢即時資料的歷史紀錄。

## 版面

以 `st.tabs` 分為四個分頁:使用者 / 權限 / 日誌 / DB 狀態。

## UI 版面規劃

寬版,`st.tabs(["使用者", "權限", "日誌", "DB 狀態"])`。頁面進入前先做 Admin gate。

```
[ 使用者 ] [ 權限 ] [ 日誌 ] [ DB 狀態 ]                 ← st.tabs
── 使用者 ──────────────────────────────────────────────
 搜尋[____] 角色[▾] 狀態[▾]                              ← filter_bar(key_prefix="admin_user")
 帳號  Email  角色  建立時間  狀態   [停用/啟用]          ← st.dataframe/逐列

── 權限 ────────────────────────────────────────────────
 使用者[▾]  角色 user ↔ admin  [ 變更 ]  → st.dialog 二次確認 + 寫日誌

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
| 權限 | `st.selectbox` + `st.dialog` 確認 | 不可將自己降為最後一個 Admin |
| 日誌 | `filter_bar(key_prefix="admin_log")` + `st.dataframe` + `pagination_controls` | 等級以狀態色著色 |
| DB 狀態 | `metric_cards()` + `st.dataframe` | 唯讀 |

---

## 功能細節

### Admin Gate

```python
from lib.state import get_actor
actor = get_actor()
if actor is None or actor.role != "admin":
    st.error("此頁面僅限 Admin 存取")
    st.stop()
```

> `build_pages` 已動態不註冊此頁,此 gate 作為**深度防禦**第二層。

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

- `st.dataframe` 列出所有使用者(帳號、Email、角色、建立時間、狀態)。
- 每列「停用」/「啟用」按鈕:以 `@st.dialog` 二次確認 → 呼叫 `PATCH /admin/users/{id}` → `st.toast` 回饋 + 刷新。
- 敏感操作後端寫稽核日誌,前端不重複記。
- API endpoint(placeholder):`GET /admin/users`。

### 權限分頁

```python
target_user = st.selectbox("選擇使用者", user_list)
new_role = st.radio("新角色", ["user", "admin"])
if st.button("變更角色"):
    # 開 st.dialog 二次確認
    ...
```

- **不可將自己降為最後一個 Admin**:後端以 `ValidationError`(422)回絕 → `st.error`「無法移除最後一位 Admin」。
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

## 資料

- 透過後端**管理 API** 存取 users / logs / records / realtime;前端不直接連 DB。
- 敏感操作(停用帳號、角色變更)呼叫對應 API,由後端寫稽核日誌。

---

## 權限規則

- 進入頁面即需 Admin;非 Admin 一律擋下(前端不註冊 + 頁面 gate + 後端再驗)。
- 角色變更、帳號停用等敏感操作需記錄於日誌。

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
| `last_request_id` | `render_error` | 管理 API 失敗時附錯誤代碼 |

---

## 狀態與錯誤處理

進入頁面的存取控制以「前端不註冊 + 頁面 gate + 後端再驗」為主;頁內操作失敗的呈現一律依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威):

| 情境 | 依 §3 呈現 |
|---|---|
| 非 Admin 直接存取 URL | 前端不註冊此頁;頁面 gate `st.error`「此頁面僅限 Admin」+ `st.stop()` |
| 敏感操作被拒(停用帳號 / 角色變更遇 403) | `PermissionDenied` → `st.error`;對明知無權的操作**預先停用按鈕** |
| 不可將自己降級為最後一個 Admin | `ValidationError`(422)→ dialog 內 `st.error`「無法移除最後一位 Admin」;變更不生效 |
| 查詢 / 載入失敗(使用者、日誌、DB 狀態) | `ApiError` → `st.error` + 保留頁框 + 可重試(附錯誤代碼) |
| 無資料(篩選後) | `empty_state()` 取代對應 `st.dataframe` |

> 敏感操作(停用帳號、角色變更)無論成功或被拒,後端一律寫稽核日誌;前端只負責依上表呈現結果。

---

## lib/ 依賴

| 模組 | 用途 |
|---|---|
| `lib/ui.py` | `filter_bar`、`metric_cards`、`pagination_controls`、`empty_state` |
| `lib/errors.py` | `render_error` |
| `lib/state.py` | `get_actor()`（Admin gate）|
| `lib/api_client.py` | 管理 API 所有讀寫呼叫 |

---

## 可測試性 / TDD

### 純函式（`tests/unit/test_admin.py`）

1. `color_log_level("ERROR")` — 回正確色彩 token（或 CSS class）；`"INFO"` / `"WARNING"` 亦覆蓋。
2. `is_last_admin(users)` — 只剩一個 admin 時回 `True`；兩個以上回 `False`。
3. `format_db_size(bytes)` — 正確格式化為 MB 字串。

### 頁面行為（`tests/app/test_admin.py`，AppTest）

4. 非 Admin（`role="user"`）進入 → 含「僅限 Admin」錯誤訊息。
5. Admin + mock → 頁面含「系統管理」標題。
6. Admin + mock → 含四分頁（使用者/權限/日誌/DB 狀態）。
7. `GET /admin/users` 失敗 → 含 `st.error` + 「錯誤代碼」。
8. 篩選後無資料 → 含 `st.info` 空狀態。

> 依 CLAUDE.md，逐一先寫失敗測試 → 最小實作 → 綠燈重構。

---

## 依賴 / 備註

- 敏感操作建議全部留稽核紀錄（後端責任）。
- Admin API endpoints 均為 placeholder，待後端對齊後填入。
