# 頁面規格:資料分析

- 頁面編號:5
- 對應模組:模組 4 資料分析
- 存取權限:已登入使用者
- 相關:[UI Helper 規格](../ui.md)、[錯誤處理規格](../error-handling.md)、[資料來源](../data-source.md)

## 目的

對歷史資料做統計、聚合與趨勢分析,並可下載 Excel。

## 版面

以 `st.tabs` 分為三個分頁:統計 / 趨勢 / 匯出。

## UI 版面規劃

寬版,`st.tabs(["統計", "趨勢", "匯出"])`;三分頁共用頂部篩選列(時間範圍 + 分類)。

```
時間範圍[起]-[迄]   分類[▾]                             ← filter_bar(key_prefix="an", show_keyword=False)

── 統計 ────────────────────────────────────────────────
 ┌────────┬────────┬────────┬────────┐
 │ 總計    │ 平均    │ 最大    │ 最小    │                ← metric_cards(4 個 Metric)
 └────────┴────────┴────────┴────────┘
 分類聚合表(groupby)  ← st.dataframe

── 趨勢 ────────────────────────────────────────────────
 粒度: (時)(日)(週)   ← st.radio/segmented
 時間序列折線圖 + 分類疊圖   ← st.line_chart / Plotly

── 匯出 ────────────────────────────────────────────────
 目前篩選：分類={category}[，期間 {from} ~ {to}]，共 {n} 筆   ← build_export_caption()
 [ ⬇ 下載 Excel (.xlsx) ]   [ ⬇ 下載 CSV ]   ← st.download_button
```

| 分頁 | 主要元件 | 備註 |
|---|---|---|
| 篩選(共用) | `filter_bar(key_prefix="an", show_keyword=False)` | 三分頁一致;`show_keyword=False` 分析不需關鍵字搜尋 |
| 統計 | `metric_cards(4 個 Metric)` + `st.dataframe` | 聚合用 pandas `agg`/`groupby` |
| 趨勢 | `st.radio`/`segmented_control` 選粒度 + `st.line_chart` | 分類疊圖比較 |
| 匯出 | `st.download_button` | 內容與畫面篩選一致;無資料時 `disabled=True` |
| 空狀態 | `empty_state()` | 範圍內無資料時停用匯出並顯示空狀態 |

---

## 功能細節

### 共用篩選列

以 `filter_bar()` 管理篩選條件(見 [UI Helper §3](../ui.md#3-filter_bar--篩選列)):

```python
from lib.ui import filter_bar, FilterParams

fp = filter_bar(
    categories=["全部", "感測器", "系統", "應用", "網路"],
    key_prefix="an",
    show_keyword=False,   # 分析不需關鍵字
)
```

- `fp` 為 `FilterParams` 快照,三分頁皆讀同一 `fp` 確保一致。
- 篩選條件改變時,統計/趨勢/匯出內容同步更新。

### 統計分頁

以 `metric_cards()` 渲染 4 個指標卡(見 [UI Helper §4](../ui.md#4-metric_cards--指標卡列)):

```python
from lib.ui import metric_cards, Metric

metric_cards([
    Metric("總計", int(df["value"].sum())),
    Metric("平均", round(df["value"].mean(), 2)),
    Metric("最大", df["value"].max()),
    Metric("最小", df["value"].min()),
])
```

- 篩選後 `df` 為空 → 不渲染指標卡,改以 `empty_state()` 取代並停用匯出按鈕。
- 分類聚合表以 `df.groupby("category")["value"].agg(["sum","mean","max","min"])` 計算,`st.dataframe` 呈現。

### 趨勢分頁

```python
granularity = st.radio("粒度", ["時", "日", "週"], horizontal=True,
                       key="an_granularity")
freq_map = {"時": "h", "日": "D", "週": "W"}
resampled = df["value"].resample(freq_map[granularity]).sum()
st.line_chart(resampled)

# 分類疊圖
pivot = df.pivot_table(values="value", index=df.index,
                       columns="category", aggfunc="sum")
st.line_chart(pivot)
```

- 資料來自 `DataSource`(mock/api);粒度對應 pandas resample freq。
- `session_state` key `an_granularity` 由 `st.radio` 自動管理。

### 匯出分頁

```python
from lib.analytics import build_export_caption, make_excel_bytes

has_data = not df.empty

if has_data:
    st.caption(build_export_caption(fp.category, fp.date_from, fp.date_to, len(df)))
    export_df = df.reset_index()
    excel_bytes = make_excel_bytes(export_df)          # 自動處理 tz-aware datetime
    csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")  # utf-8-sig 讓 Excel 正確開啟
else:
    empty_state()
    excel_bytes, csv_bytes = b"", b""

st.download_button("⬇ 下載 Excel (.xlsx)",
                   data=excel_bytes, file_name="analysis.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   disabled=not has_data)
st.download_button("⬇ 下載 CSV",
                   data=csv_bytes, file_name="analysis.csv",
                   mime="text/csv",
                   disabled=not has_data)
```

- **篩選摘要**：`build_export_caption(category, date_from, date_to, count)` 回傳格式：
  `目前篩選：分類={category}[，期間 {from} ~ {to}]，共 {n} 筆`；無設定的日期端以「—」表示。
- **無資料時 `disabled=True`**，防止下載空檔案。
- `make_excel_bytes` 自動將 tz-aware datetime 轉為 UTC naive（Excel 不支援時區）。
- `openpyxl` 需在 `requirements.txt` 中。
- 內容與目前篩選條件一致，不另呼叫 API（以 `df` 為準）。

---

## 資料

- 讀取:透過後端**分析 API** 取得原始 records(依時間範圍與分類篩選),前端 pandas 計算聚合/趨勢;前端不直接連 DB。
- API endpoint(placeholder,待後端對齊):`GET /records?from={date_from}&to={date_to}&category={category}&size=5000`。
- 全量下載後前端 pandas 聚合,避免後端多個分析端點的維護成本;若資料量過大後端可提供分析端點再切換。
- 唯讀頁面。

---

## Mock 模式行為(`DATA_SOURCE=mock`)

- 直接呼叫 `MockDataSource.list_records(page=1, size=1000)` 取得假記錄。
- 時間篩選:`fp.date_from` / `fp.date_to` 以 `record.created_at.date()` 過濾。
- 分類篩選:`fp.category != "全部"` 時以 `record.category == fp.category` 過濾。
- 統計與趨勢在前端 pandas 計算,**不呼叫任何網路**。
- `DATA_SOURCE=api` 後無縫切換至真實 API,頁面邏輯不改。

---

## session_state 契約

使用 `an_` 前綴(見 [UI Helper §7](../ui.md#7-狀態命名規範) 與 [應用骨架 §7](../app-skeleton.md#7-session_state-契約單一真相)):

| Key | 由誰管理 | 說明 |
|---|---|---|
| `an_category` | `filter_bar()` | 分類篩選（含「全部」） |
| `an_date_from` | `filter_bar()` | 起始日期 |
| `an_date_to` | `filter_bar()` | 結束日期 |
| `an_granularity` | `st.radio` | 趨勢粒度（時/日/週） |
| `last_request_id` | `render_error` | 分析 API 失敗時附錯誤代碼 |

---

## 狀態與錯誤處理

呈現一律依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威),不自訂層級 / 文案:

| 情境 | 依 §3 呈現 |
|---|---|
| 範圍內無資料 | `empty_state()` 取代統計 / 圖表區,並**停用匯出**按鈕 |
| 分析 API 查詢失敗 / 逾時 | `ApiError` → `st.error` + 保留頁框 + 可重試(附錯誤代碼);同時**停用匯出** |
| 大範圍查詢 | 建議快取(`@st.cache_data(ttl=60)`)以降低重查;**不可**把 `request_id` 放進快取 key(見 [request-id §5](../request-id.md)) |

---

## lib/ 依賴

| 模組 | 用途 |
|---|---|
| `lib/analytics.py` | `records_to_df`、`agg_stats`、`agg_by_category`、`resample_series`、`filter_by_date`、`make_excel_bytes`、`build_export_caption` |
| `lib/ui.py` | `filter_bar`、`metric_cards`、`empty_state` |
| `lib/errors.py` | `render_error` |
| `lib/data_source.py` | `get_data_source()` |
| `lib/api_client.py` | `DATA_SOURCE=api` 時查詢 records |

外部套件:
- `pandas`（已存在）
- `openpyxl`（已加入 `requirements.txt`，Excel 匯出用）

---

## 可測試性 / TDD

純邏輯抽到 `lib/`；頁面以 `AppTest` 驗互動行為。

### 純函式（`tests/unit/test_analytics.py`）

1. `agg_stats(df)` — 輸入 DataFrame，回傳 `{sum, mean, max, min}`；空 df → 全為 `None`。
2. `agg_by_category(df)` — groupby category 回 DataFrame；空 df → 空 DataFrame。
3. `resample_series(df, "D")` — 以日粒度聚合，index 為 date；驗正確筆數與值。
4. `filter_by_date(df, date_from, date_to)` — 時間範圍正確過濾。
5. `filter_by_category(df, "感測器")` — 分類正確過濾；`"全部"` → 不過濾。
6. `make_excel_bytes(df)` — 回傳非空 bytes；`df.empty` 時也不拋例外。
7. `build_export_caption(category, date_from, date_to, count)` — 格式驗證：無日期時不含「期間」；有單邊日期時另一端以「—」表示；完整日期與分類、筆數均出現在輸出字串中。

### 頁面行為（`tests/app/test_analytics.py`，AppTest）

7. 全 mock 下進入分析頁 → 含「資料分析」標題。
8. mock 有資料 → 含 4 個 `st.metric`（統計指標卡）。
9. 無資料（空篩選結果）→ 含 `st.info` 空狀態，匯出按鈕 `disabled`。
10. `api_client` 回 `ApiError` → 含 `st.error` + 「錯誤代碼」，匯出 disabled。
11. 趨勢分頁 → 粒度選擇（時/日/週）radio 可切換，折線圖重繪。

> 依 CLAUDE.md，逐一先寫失敗測試 → 最小實作 → 綠燈重構。

---

## 依賴 / 備註

- 匯出內容需與畫面篩選一致。
- `openpyxl` 加入 `requirements.txt`。
- 大範圍查詢（如跨年）前端 pandas 可能壓力大，未來可改由後端提供分析端點；本規格先走前端聚合。
