# 頁面規格:系統管理

- 頁面編號:6
- 對應模組:模組 5 系統管理
- 存取權限:**僅 `grade >= AdminRole.SUPER_ADMIN`（≥100，含 ROOT=999）**（`editor` / `viewer` 不可見；由 `build_pages(actor)` 動態不註冊，比隱藏連結更安全）。存取軸的權威定義見[前端頁面結構 §存取控制](../frontend-pages.md#存取控制本節為存取軸的單一真相)。
- 導覽:`build_pages(actor)` 僅在 `actor.grade >= AdminRole.SUPER_ADMIN` 時追加此頁——見[應用骨架 §5](../app-skeleton.md#5-導覽與頁面註冊build_pages)
- 相關:[UI Helper 規格](../ui.md)、[錯誤處理規格](../error-handling.md)

## 目的

提供 Admin 查閱系統日誌與資料庫狀態。

> **管理員管理功能已移至主前端（Next.js CMS）實作**，Streamlit 端不再提供此分頁。

## 版面

以 `st.tabs` 分為兩個分頁:日誌 / DB 狀態。

## UI 版面規劃

寬版，`st.tabs(["日誌", "DB 狀態"])`。兩分頁皆唯讀。

```
[ 日誌 ] [ DB 狀態 ]                                         ← st.tabs

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
| 日誌 | `filter_bar(key_prefix="admin_log")` + `st.dataframe` + `pagination_controls` | 等級以狀態色著色 |
| DB 狀態 | `metric_cards()` + `st.dataframe` | 唯讀 |

---

## 功能細節

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

> **重要**:`MockDataSource` 目前**只支援 records CRUD**,不含 logs / db-status。本頁 mock 階段的資料由 `lib/system_management.py` 的**靜態種子 + 純函式**提供,不呼叫網路;換 `DATA_SOURCE=api` 後才改打管理 API。

| 分頁 | Mock 資料來源 |
|---|---|
| 日誌 | `seed_logs()` 靜態假日誌（含 INFO/WARNING/ERROR） |
| DB 狀態 | `seed_db_status()` 靜態假指標（連線正常、表列數、DB 大小） |

- 兩分頁皆唯讀，無寫入操作，無可變 session_state。
- mock 模式下**不需登入 BFF** 亦可完整呈現；可直接以 AppTest 驗證。

---

## `lib/system_management.py` 純函式契約（單一真相）

所有函式**無 Streamlit 依賴**,可直接單元測試。

| 函式 | 簽章 | 契約 |
|---|---|---|
| `color_log_level` | `(level: str) -> str` | `"ERROR"` / `"WARNING"` / `"INFO"` → 對應色彩 token(或 CSS class);未知等級回中性色。 |
| `format_db_size` | `(size_bytes: int) -> str` | 位元組 → `"{:.1f} MB"`(或適當單位)字串;`0 → "0.0 MB"`。 |
| `seed_logs` / `seed_db_status` | `() -> list` / `() -> dict` | mock 靜態種子;決定性、不依賴時鐘。 |

---

## 資料

- 透過後端**管理 API** 存取 logs / db-status；前端不直接連 DB。
- 兩分頁皆唯讀。

---

## 權限規則

- **頁面進入**：`grade >= AdminRole.SUPER_ADMIN`（≥100）才可見此頁（由 `build_pages` 動態不註冊）。
- **日誌 / DB 狀態分頁**：所有進入者皆可讀取，無寫入。

---

## session_state 契約

使用頁面前綴(見 [UI Helper §7](../ui.md#7-狀態命名規範)):

| Key | 前綴 | 由誰管理 | 說明 |
|---|---|---|---|
| `admin_log_category` | `admin_log_` | `filter_bar()` | 日誌分頁等級篩選 |
| `admin_log_date_from` | `admin_log_` | `filter_bar()` | 日誌分頁起始日期 |
| `admin_log_date_to` | `admin_log_` | `filter_bar()` | 日誌分頁結束日期 |
| `admin_log_page` | `admin_log_` | `pagination_controls()` | 日誌分頁當前頁碼 |
| `last_request_id` | — | `render_error` | 管理 API 失敗時附錯誤代碼 |

---

## 狀態與錯誤處理

頁內所有操作失敗的呈現一律依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威):

| 情境 | 依 §3 呈現 |
|---|---|
| grade≥100 進入 | 頁面正常渲染（兩分頁皆可用），不出現「僅限 Admin」錯誤 |
| 查詢 / 載入失敗（日誌、DB 狀態） | `ApiError` → `st.error` + 保留頁框 + 可重試（附錯誤代碼） |
| 無資料（篩選後） | `empty_state()` 取代對應 `st.dataframe` |

---

## lib/ 依賴

| 模組 | 用途 |
|---|---|
| `lib/ui.py` | `filter_bar`、`metric_cards`、`pagination_controls`、`empty_state` |
| `lib/system_management.py` | `color_log_level`、`format_db_size`、`seed_logs`、`seed_db_status` |
| `lib/models.py` | `AdminRole` 常數（grade 數值比較） |
| `lib/errors.py` | `render_error`（接後端後才引入） |
| `lib/api_client.py` | 管理 API 呼叫（接後端後才引入） |

---

## 可測試性 / TDD

### 純函式（`tests/unit/test_system_management.py`）

1. `color_log_level("ERROR")` — 回正確色彩 token（或 CSS class）；`"INFO"` / `"WARNING"` / 未知等級亦覆蓋。
2. `format_db_size(bytes)` — 正確格式化為 MB 字串（含 `0 → "0.0 MB"`）。

### 頁面行為（`tests/app/test_system_management.py`，AppTest）

3. super_admin + mock → 頁面含「系統管理」標題與**兩個**分頁（日誌 / DB 狀態），**不**含「管理員管理」、「使用者」或「權限」分頁。
4. DB 狀態分頁含 `metric_cards`（連線狀態、各表列數、DB 大小）。
5. 日誌分頁渲染種子日誌（無 exception）。
6. 日誌分頁日期篩選型別安全：注入 `admin_log_date_range=(date(2025,1,1), date(2025,12,31))` → 無 exception；種子日誌時間均在 2024 年，故 2025 年範圍無符合記錄 → `empty_state`（「無符合條件的日誌」）。（回歸：`date` 物件與字串混合 `<=` 比較已修正為 `str(date)` 做字典序比對。）

> 依 CLAUDE.md，逐一先寫失敗測試 → 最小實作 → 綠燈重構。先做 `lib/system_management.py` 純函式（unit 1–2）→ 頁面（AppTest 3–6）。

---

## API Endpoints（對應後端 `/admin/...`）

| 操作 | 方法 & 路徑 | 請求 / 回應 |
|---|---|---|
| 日誌列表 | `GET /admin/logs?from=&to=&user=&level=&page=&size=` | log list |
| DB 狀態 | `GET /admin/db/status` | 連線狀態、各表列數、DB 大小 |
| 歷史記錄 | `GET /admin/records/history` | st.dataframe |

## 依賴 / 備註

- 管理員管理（建立／改名／升降權／封存／刪除）已移至主前端 CMS（Next.js），後端 `/admin/admins/...` API 由主前端直接呼叫，Streamlit 不參與。
