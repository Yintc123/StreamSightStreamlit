# 規格:共用 UI Helper(`lib/ui.py`)

跨頁重複的薄 UI 元件集中於此，供 `pages/` 直接呼叫，避免各頁各自實作差異版本。

- **原則**:純邏輯(資料轉換、頁碼計算、篩選條件組合)抽純函式放本檔，UI 綁定（`st.*` 呼叫）只作薄包裝。
- **前提**:見 [應用骨架 §6](app-skeleton.md#6-lib-分層總表單一入口地圖)；錯誤呈現一律走 [`lib/errors.py`](error-handling.md)，不在此重複。
- **放置**:`lib/ui.py`；對應測試：`tests/unit/test_ui.py`（純函式）與 `tests/app/`（AppTest 頁面行為）。

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
from dataclasses import dataclass, field
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
- **狀態**：以 `key_prefix` 為命名空間在 `session_state` 讀寫目前篩選值（例如 `{key_prefix}_category`），避免多頁衝突。
- 每次 rerun 讀取目前 `session_state` 值作為元件預設，並在元件值改變時自動更新（`on_change` 或 Streamlit 元件天然回寫）。
- 回傳本次 rerun 的 `FilterParams` 快照；**呼叫端**據此傳入資料查詢，不直接操作 `session_state`。

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
    size: int,
    key_prefix: str,
) -> int:   # 回傳當前頁碼（1-based）
```

### 行為

- 計算 `total_pages = ceil(total / size)`。
- 以 `{key_prefix}_page`（`session_state` key）存目前頁碼，初始值 `1`。
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

1. `FilterParams` 預設值正確（`category="全部"`、`keyword=""`、日期 `None`）。
2. `_page_caption(1, 5, 47)` → `"第 1 / 5 頁 · 共 47 筆"`。
3. `_clamp_page(0, 3)` → `1`；`_clamp_page(10, 3)` → `3`；`_clamp_page(2, 3)` → `2`。
4. `metric_cards([])` 不拋例外（靜默）。

### AppTest（`tests/app/test_ui_components.py`）

5. `filter_bar` 初始渲染包含 selectbox、text_input。
6. `filter_bar` 不同 `key_prefix` 不互相污染（兩組元件共存於同頁）。
7. `pagination_controls(total=0, ...)` 不渲染任何元件。
8. `pagination_controls` 首頁時上一頁 disabled；末頁時下一頁 disabled。

---

## 9. 相關文件

- [應用骨架 §6](app-skeleton.md#6-lib-分層總表單一入口地圖)（lib 分層地圖）
- [錯誤處理規格](error-handling.md)（`render_error` / `empty_state` 的錯誤邊界）
- [設計系統](design-system.md)（色彩 token、元件樣式指引）
- [前端頁面結構](frontend-pages.md)（各頁使用情境）
