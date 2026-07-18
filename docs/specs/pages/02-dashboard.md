# 頁面規格:儀表板 / 首頁

- 頁面編號:2
- 對應模組:總覽(彙整模組 2~4)
- 存取權限:已登入使用者
- 導覽:登入後預設頁面
- 相關:[前端頁面結構](../frontend-pages.md)、[UI Helper 規格](../ui.md)、[錯誤處理規格](../error-handling.md)、[資料來源](../data-source.md)

## 目的

提供一眼掌握系統現況的總覽:關鍵指標、最新告警、即時趨勢縮圖,作為進入各功能的起點。

## 版面

- 頂部:4 個關鍵指標卡(`metric_cards()`)。
- 中段:最近告警清單。
- 下段:即時趨勢縮圖圖表。

## UI 版面規劃

寬版單欄,由上而下:指標列 → 兩欄(告警 / 趨勢)。

```
┌────────────────────────────────────────────────────────────┐
│ 儀表板                                    歡迎,{username}    │  ← st.title + 右上問候
├──────────┬──────────┬──────────┬──────────────────────────┤
│ 資料總筆數│ 今日新增  │ 進行中告警│ 線上使用者                │  ← metric_cards(4 個 Metric)
│  12,340  │  +128    │   3 ⚠    │   5                      │
├──────────┴──────────┴──────────┼──────────────────────────┤
│ 最近告警                         │ 即時趨勢縮圖              │  ← st.columns([1.2, 1])
│ ┌────────────────────────────┐ │ ┌──────────────────────┐ │
│ │ 時間  分類  數值  閾值 →跳轉 │ │ │   折線縮圖 (line_chart)│ │  ← st.fragment(run_every)
│ │ ...最新 N 筆                │ │ │                      │ │
│ └────────────────────────────┘ │ └──────────────────────┘ │
└────────────────────────────────┴──────────────────────────┘
```

| 區域 | 元件 | 備註 |
|---|---|---|
| 指標列 | `metric_cards(metrics)` | 進行中告警 > 0 時 `delta_color="inverse"` 標紅(見下方細節) |
| 最近告警 | `st.dataframe` 或列表 | 點列跳轉即時監控(`st.switch_page`) |
| 趨勢縮圖 | `st.fragment(run_every=30)` + `st.line_chart` | 定時刷新,唯讀 |
| 空狀態 | `empty_state()` | 無資料時取代對應區塊 |

---

## 功能細節

### 關鍵指標卡

以 `metric_cards()` 渲染,傳入 4 個 `Metric`(見 [UI Helper §4](../ui.md#4-metric_cards--指標卡列)):

```python
from lib.ui import metric_cards, Metric, empty_state

metric_cards([
    Metric("資料總筆數", total_count),
    Metric("今日新增", today_added, delta=f"+{today_added}", delta_color="normal"),
    Metric("進行中告警", active_alerts,
           delta_color="inverse" if active_alerts > 0 else "off"),   # > 0 標紅
    Metric("線上使用者", online_users),
])
```

| 指標 | 來源 API(placeholder,待後端對齊) | `delta_color` 規則 |
|---|---|---|
| 資料總筆數 | `GET /dashboard/summary` → `total_count` | `"off"` |
| 今日新增 | `GET /dashboard/summary` → `today_added` | `"normal"` |
| 進行中告警 | `GET /dashboard/summary` → `active_alerts` | `> 0 → "inverse"`;`= 0 → "off"` |
| 線上使用者 | `GET /dashboard/summary` → `online_users`(可選,若後端有 session 心跳) | `"off"` |

- 查詢失敗時**不渲染指標卡**,改以 `render_error(exc)` 呈現;見[錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威)。

### 快取策略

指標卡資料以 `@st.cache_data(ttl=30)` 快取(30 秒),避免每次 rerun 重查;寫入後請在寫入 API 成功後呼叫 `st.cache_data.clear()` 使快取失效。趨勢縮圖以 `st.fragment(run_every=30)` 定時刷新。

### 最近告警

- 顯示最新 N 筆告警(時間、分類、數值、閾值)。
- 點擊可跳轉即時監控頁(`st.switch_page("pages/realtime_monitor.py")`)。
- 告警列表來源:`GET /dashboard/alerts`(placeholder)。

### 即時趨勢縮圖

- 顯示近期數值折線縮圖(預設近 1 小時)。
- 以 `st.fragment(run_every=30)` 每 30 秒重取最新資料點更新圖表,避免整頁 rerun。
- 來源:`GET /dashboard/trend`(placeholder)。

---

## Mock 模式行為(`DATA_SOURCE=mock`)

- **指標卡**:使用 `MockDataSource.list_records()` 計算 `total_count`;`today_added` / `active_alerts` / `online_users` 以硬寫靜態假值(`today_added=3`、`active_alerts=1`、`online_users=2`)呈現,標示 `(mock)` caption。
- **告警列表**:從 `MockDataSource` 取最新 5 筆 record 模擬告警,不呼叫網路。
- **趨勢縮圖**:以 `MockDataSource` 全部 records 的 `value` 按建立時間排序產生假折線,`run_every` 靜態不更新。
- mock 模式下**不需登入 BFF** 亦可完整呈現;換 `DATA_SOURCE=api` 後才呼叫真實 API。

---

## 資料

- 讀取:透過後端 API 取得彙總指標、最新告警與趨勢資料;前端不直接連 DB。
- 唯讀頁面,不做寫入。

---

## session_state 契約

儀表板無自有頁面私有狀態;只讀全域 `actor`(見[應用骨架 §7](../app-skeleton.md#7-session_state-契約單一真相)):

| Key | 來源 | 用途 |
|---|---|---|
| `actor` | `lib/state.get_actor()` | 顯示「歡迎,{username}」問候語 |
| `last_request_id` | `lib/errors.render_error` 寫入 | 儀表板 API 失敗時附錯誤代碼 |

---

## 狀態與錯誤處理

呈現依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威):

| 情境 | 呈現 |
|---|---|
| 指標卡查詢失敗 / 逾時 | `ApiError` → `st.error` + 保留頁面框架 + 可重試(附錯誤代碼) |
| 告警列表查詢失敗 | 同上 |
| 趨勢縮圖查詢失敗 | 同上,縮圖區以錯誤訊息取代 |
| 無資料(指標全零 / 無告警 / 無趨勢) | `empty_state()` 取代對應區塊;**非**錯誤 |

---

## lib/ 依賴

| 模組 | 用途 |
|---|---|
| `lib/ui.py` | `metric_cards`、`empty_state` |
| `lib/errors.py` | `render_error` |
| `lib/state.py` | `get_actor()` 取問候用戶名 |
| `lib/data_source.py` | `get_data_source()` → mock 模式下取 MockDataSource |
| `lib/api_client.py` | `DATA_SOURCE=api` 時查詢指標/告警/趨勢 |

---

## 可測試性 / TDD

純邏輯抽到 `lib/`(見 CLAUDE.md);頁面以 `AppTest` 驗互動行為。

### 純函式(`tests/unit/`)

1. `Metric("進行中告警", 3, delta_color="inverse")` — `delta_color` 正確傳遞至 `metric_cards`(可直接測 `Metric` dataclass)。
2. mock 模式下 `get_data_source()` 回 `MockDataSource`,能呼叫 `list_records()` 取假資料。

### 頁面行為(`tests/app/test_dashboard.py`，AppTest)

3. 全 mock 下進入儀表板 → 頁面含「儀表板」標題。
4. 全 mock 下 → 含 4 個 `st.metric` 元件(指標卡)。
5. 全 mock 下 → 含問候語「歡迎」+使用者名(Alice)。
6. mock 資料有 records → 顯示告警列表,**不**顯示 `empty_state`。
7. `api_client` 回 `ApiError` → 頁面含 `st.error` 且含「錯誤代碼」。
8. 告警數 > 0 的 `Metric.delta_color` 為 `"inverse"`(透過注入假指標值驗證)。

> 依 CLAUDE.md,逐一先寫失敗測試 → 最小實作 → 綠燈重構。

---

## 效能 / 依賴備註

- 指標建議 `@st.cache_data(ttl=30)` 避免每次 rerun 重查。
- 趨勢縮圖以 `st.fragment(run_every=30)` 局部刷新,避免全頁重繪。
- 唯讀,無寫入 API 呼叫。
