# 規格:共用 UI Helper(`lib/ui.py`)

跨頁重複的薄 UI 元件集中於此，供 `pages/` 直接呼叫，避免各頁各自實作差異版本。

- **原則**:純邏輯(資料轉換、頁碼計算、篩選條件組合)抽純函式放本檔，UI 綁定（`st.*` 呼叫）只作薄包裝。
- **前提**:見 [應用骨架 §6](app-skeleton.md#6-lib-分層總表單一入口地圖)；錯誤呈現一律走 [`lib/errors.py`](error-handling.md)，不在此重複。
- **放置**:`lib/ui.py`；對應測試：`tests/unit/test_ui.py`（純函式）與 `tests/app/test_ui_components.py`（AppTest 頁面行為）。

---

## 1. 元件一覽

| 函式 | 出現頁面 | 回傳 | 說明 |
|---|---|---|---|
| `filter_bar(categories, key_prefix)` | 資料管理、分析、Admin | `FilterParams` | 篩選列 UI，內部管理 session_state |
| `metric_cards(metrics)` | 儀表板、分析、Admin | `None` | `st.columns + st.metric` 指標卡列 |
| `pagination_controls(total, size, key_prefix)` | 資料管理、Admin | `int`（當前頁碼） | 上/下頁按鈕 + 頁碼 caption |
| `empty_state(message)` | 全部頁面 | `None` | 查無資料時的 `st.info` 標準佔位 |

---

## 2. 型別定義

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Optional, List
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal


@dataclass
class FilterParams:
    """篩選條件快照；純資料，無 UI 依賴，可直接單元測試。"""
    category: str = "全部"   # "全部" 代表不篩選
    keyword: str = ""
    date_from: Optional[date] = None
    date_to: Optional[date] = None


@dataclass
class Metric:
    """單一指標卡資料；純資料，可直接單元測試。"""
    label: str
    value: int | float | str
    delta: Optional[int | float | str] = None
    delta_color: Literal["normal", "inverse", "off"] = "normal"
    help: Optional[str] = None
```

- `FilterParams` 與 `Metric` 為純資料類別，**不依賴 Streamlit**，可直接被單元測試驗證。

---

## 3. `filter_bar` — 篩選列

### 簽章

```python
def filter_bar(
    categories: List[str],
    key_prefix: str,
    show_date: bool = True,
    show_keyword: bool = True,
) -> FilterParams:
```

### 行為

- 渲染：`st.columns` 並列 `st.selectbox`（分類）、`st.date_input`（時間範圍，若 `show_date`）、`st.text_input`（關鍵字，若 `show_keyword`）。
- **狀態初始化**：首次 rerun 時以 `session_state.setdefault(key, default)` 確保各 key 存在，預設值對應 `FilterParams` 欄位的預設（`category` → `categories[0]`、`keyword` → `""`、`date_from` / `date_to` → `None`）。
- 每次 rerun 讀取目前 `session_state` 值作為元件預設，並在元件值改變時自動更新（`on_change` 或 Streamlit 元件天然回寫）。
- 回傳本次 rerun 的 `FilterParams` 快照；**呼叫端**據此傳入資料查詢，不直接操作 `session_state`。
- **與分頁的互動**：若同一頁同時使用 `pagination_controls`（共用相同 `key_prefix`），呼叫端應在偵測到篩選條件改變時（即本次快照 ≠ 上次快照）將 `{key_prefix}_page` 重設為 `1`，避免使用者停在無效的高頁碼。建議做法：將前次 `FilterParams` 存於 `session_state`，與本次比較，若不同則 `st.session_state[f"{key_prefix}_page"] = 1`。

### 分類清單慣例

各頁傳入自訂 `categories`，第一個選項慣例為 `"全部"`（代表不篩選）：

```python
# 資料管理
filter_bar(["全部", "感測器", "系統", "應用", "網路"], key_prefix="dm")
# 分析
filter_bar(["全部", "感測器", "系統"], key_prefix="an", show_keyword=False)
# Admin 日誌
filter_bar(["全部", "INFO", "WARNING", "ERROR"], key_prefix="admin_log")
```

---

## 4. `metric_cards` — 指標卡列

### 簽章

```python
def metric_cards(metrics: List[Metric]) -> None:
```

### 行為

- 依 `len(metrics)` 動態建立 `st.columns(n)`，每欄呼叫 `st.metric`。
- `delta_color` 直接傳給 `st.metric`；`help` 非空時傳入 `help=`。
- `metrics` 為空 → 不渲染（靜默）。
- 指標卡本身**不處理錯誤**；呼叫端在資料取得失敗時應呼叫 `render_error(exc)` 並跳過 `metric_cards`。

### 使用範例

```python
# 儀表板
metric_cards([
    Metric("資料總筆數", 12340),
    Metric("今日新增", 128, delta="+128", delta_color="normal"),
    Metric("進行中告警", 3, delta_color="inverse"),
    Metric("線上使用者", 5),
])
```

---

## 5. `pagination_controls` — 分頁控制

### 簽章

```python
def pagination_controls(
    total: int,
    size: int,   # 前置條件：size >= 1
    key_prefix: str,
) -> int:   # 回傳當前頁碼（1-based）
```

### 行為

- **前置條件**：`size >= 1`（呼叫端保證；傳入 0 行為未定義）。
- 計算 `total_pages = ceil(total / size)`。
- 以 `{key_prefix}_page`（`session_state` key）存目前頁碼，首次以 `setdefault` 初始值 `1`。
- 每次渲染前先呼叫 `_clamp_page`，確保儲存的頁碼在 `[1, total_pages]` 內（資料筆數減少或篩選條件重置後頁碼可能越界）。
- 渲染：`st.columns([1, 6, 1])` — 左欄「‹ 上一頁」按鈕、中欄 `st.caption`、右欄「下一頁 ›」按鈕。
  - caption 格式：`第 {page} / {total_pages} 頁 · 共 {total} 筆`。
  - 首頁時左按鈕 `disabled=True`；末頁時右按鈕 `disabled=True`。
  - 按鈕點擊更新 `session_state` 並 rerun（Streamlit 天然行為）。
- `total == 0` → 不渲染（靜默）；呼叫端改顯示 `empty_state()`。
- 回傳本次 rerun 的當前頁碼供呼叫端帶入查詢。

### 純函式（可單元測試）

```python
def _page_caption(page: int, total_pages: int, total: int) -> str:
    """回傳 caption 字串，不依賴 Streamlit，供單元測試。"""
```

```python
def _clamp_page(page: int, total_pages: int) -> int:
    """確保頁碼在 [1, total_pages] 內（資料異動後頁碼可能越界）。"""
```

---

## 6. `empty_state` — 空狀態佔位

### 簽章

```python
def empty_state(message: str = "目前沒有符合條件的資料") -> None:
```

### 行為

- 直接呼叫 `st.info(message)`，作為各頁無資料時的**一致呈現**。
- 不做任何邏輯，只統一訊息文案與 UI 層級。

---

## 7. 狀態命名規範

所有使用 `session_state` 的元件以 `{key_prefix}_` 為 namespace，避免跨頁污染：

| key | 說明 |
|---|---|
| `{prefix}_category` | 篩選列目前分類 |
| `{prefix}_keyword` | 篩選列目前關鍵字 |
| `{prefix}_date_from` | 篩選列起始日期 |
| `{prefix}_date_to` | 篩選列結束日期 |
| `{prefix}_page` | 分頁列目前頁碼 |

- `key_prefix` 建議採頁面縮寫：`dm`（資料管理）、`an`（分析）、`rt`（即時監控）、`admin_*`（Admin 各分頁）。

---

## 8. 可測試性 / TDD

### 純函式（`tests/unit/test_ui.py`）

| # | 測試 | 斷言 |
|---|---|---|
| 1 | `FilterParams` 預設值 | `category="全部"`, `keyword=""`, `date_from=None`, `date_to=None` |
| 2 | `Metric` 預設值 | `delta=None`, `delta_color="normal"`, `help=None` |
| 3 | `_page_caption(1, 5, 47)` | `"第 1 / 5 頁 · 共 47 筆"` |
| 4 | `_clamp_page(0, 3)` | `1`（下界） |
| 5 | `_clamp_page(10, 3)` | `3`（上界） |
| 6 | `_clamp_page(2, 3)` | `2`（正常值不變） |

### AppTest（`tests/app/test_ui_components.py`）

| # | 測試 | 斷言 |
|---|---|---|
| 7 | `empty_state("查無資料")` | 頁面含 `st.info` |
| 8 | `metric_cards([])` | 不拋例外（靜默不渲染） |
| 9 | `metric_cards([Metric("總計", 10)])` | 頁面含對應 metric 元件 |
| 10 | `pagination_controls(total=0, size=20, key_prefix="t")` | 不渲染任何元件 |
| 11 | `pagination_controls` 首頁 | 上一頁按鈕 `disabled=True` |
| 12 | `pagination_controls` 末頁 | 下一頁按鈕 `disabled=True` |
| 13 | `filter_bar` 初始渲染 | 頁面含 selectbox、text_input |
| 14 | `filter_bar(show_date=False, ...)` | 頁面無 date_input |
| 15 | `filter_bar(show_keyword=False, ...)` | 頁面無對應 text_input |
| 16 | 兩組不同 `key_prefix` 的 `filter_bar` 共存 | 設定 prefix-A 的 category → 讀取 prefix-B 的 `session_state["{prefix_b}_category"]`，值仍為初始值 `"全部"`（各自 namespace 獨立） |
| 17 | `filter_bar` 篩選值改變後 `pagination_controls` 頁碼重置 | 先停在第 2 頁，改變分類後 `session_state["{prefix}_page"]` 回到 `1` |

---

## 9. TDD 落地順序（Red → Green → Refactor）

嚴格按 Red-Green-Refactor 循環，每次只推進一個行為：

### Phase 1 — 純資料型別（無 Streamlit 依賴）
- 測試 `FilterParams` 預設值（測試 #1）
- 測試 `Metric` 預設值（測試 #2）

### Phase 2 — 純函式
- 測試 `_page_caption` 格式（測試 #3）
- 測試 `_clamp_page` 邊界（測試 #4、#5、#6）

### Phase 3 — `empty_state`（最薄 UI 綁定）
- 測試 #7

### Phase 4 — `metric_cards`
- 測試 #8（空 list 靜默）→ 測試 #9（含 Metric 渲染）

### Phase 5 — `pagination_controls`
- 測試 #10（total=0 靜默）→ 測試 #11（首頁 disabled）→ 測試 #12（末頁 disabled）

### Phase 6 — `filter_bar`
- 測試 #13（初始渲染）→ 測試 #14（show_date=False）→ 測試 #15（show_keyword=False）→ 測試 #16（不同 prefix 不污染）→ 測試 #17（篩選改變時頁碼重置）

### Phase 7 — 遷移既有頁面（在綠燈保護下替換）

> **`pages/data_management.py` 已完成遷移（見 §10）**；其他頁面（analytics、admin）有待同步。

---

## 10. 既有頁面遷移

### `pages/data_management.py`（已完成）

資料管理頁的工具列需要四種**不同觸發模式**（分類/排序/每頁筆數即時；關鍵字需按搜尋），`filter_bar` 的設計不支援此混合模式，因此**改為內嵌佈局**，並直接使用 `empty_state` 與 `pagination_controls`。

| 元件 | 狀態 | 說明 |
|---|---|---|
| `empty_state` | ✅ 已替換 | 取代內聯 `st.info` |
| `pagination_controls` | ✅ 已替換 | 取代手工分頁邏輯 |
| `filter_bar` | ✅ 不採用 | 工具列改為 `st.columns([2,2,1,3])` 四元件內嵌；分類/排序/每頁筆數即時觸發，關鍵字以 `st.form` 包裹 |

詳見[資料管理頁規格](pages/03-data-management.md#元件細節)。

---

## 11. 相關文件

- [應用骨架 §6](app-skeleton.md#6-lib-分層總表單一入口地圖)（lib 分層地圖）
- [錯誤處理規格](error-handling.md)（`render_error` / `empty_state` 的錯誤邊界）
- [設計系統](design-system.md)（色彩 token、元件樣式指引）
- [前端頁面結構](frontend-pages.md)（各頁使用情境）
- [資料管理頁規格](pages/03-data-management.md)（`pagination_controls` / `empty_state` 使用方；工具列採內嵌佈局）
