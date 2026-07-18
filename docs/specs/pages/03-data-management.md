# 頁面規格:資料管理(UI 規格)

- 頁面編號:3
- 對應模組:模組 2 資料管理
- 存取權限:已登入(讀取/建立皆可;**編輯/刪除限該筆創建者或 Admin**)
- 導覽:一般使用者可見
- 相關:[前端頁面結構](../frontend-pages.md)、[設計系統](../design-system.md)、[功能能力對照](../feature-capability.md)、[資料來源抽象層(Mock 先行)](../data-source.md)、[ADR 0002](../decisions/0002-streamlit-as-api-client.md)

## 目的

提供資料的建立(C)、讀取(R)、更新(U)、刪除(D)與批量匯入(CSV/JSON),並以權限控制編輯與刪除。**所有資料存取一律經 `lib/api_client.py` 呼叫 FastAPI,前端不直接連 DB。**

> **開發策略**:第一階段先以 **mock data** 呈現(不接後端),資料來源抽象為 `DataSource` 介面,頁面只依賴介面;日後換真實 API 時頁面零改動。詳見[資料來源抽象層規格](../data-source.md)。

---

## 版面總覽

寬版單欄(`layout="wide"`),頁首 + `st.tabs` 三分頁:

```
┌──────────────────────────────────────────────────────────────┐
│ 資料管理                                        [ + 新增資料 ]  │  ← st.title + 快捷鈕(切到新增分頁)
├──────────────────────────────────────────────────────────────┤
│ [ 列表 ]   [ 新增 ]   [ 匯入 ]                                  │  ← st.tabs
└──────────────────────────────────────────────────────────────┘
側邊欄(僅 mock):[目前使用者 ▾ Alice(一般)/Bob(一般)/Admin]  ← 開發用切換器
```

| 分頁 | 目的 | 對應 CRUD |
|---|---|---|
| 列表 | 讀取、篩選、排序、分頁、逐列編輯/刪除 | R / U / D 入口 |
| 新增 | 單筆建立 | C |
| 匯入 | CSV / JSON 批量建立 | C(批量) |

> **目前使用者(Actor)**:mock 階段由側邊欄「開發用切換器」提供,寫入 `st.session_state["actor"]`(`{username, role}`);頁面的權限判斷與新增的 `created_by` 皆取自此。換真實 API 後改由認證(Design B)提供,切換器移除。詳見[資料來源規格](../data-source.md)。

---

## UI 元件清單(核心)

> 命名穩定性:需要 CSS 狙擊的容器一律加 `key=`(見[設計系統](../design-system.md)「狙擊特定元素」)。

| 區塊 | Streamlit 元件 | 關鍵參數 / 說明 |
|---|---|---|
| 頁首標題 | `st.title` / `st.header` | 「資料管理」 |
| 分頁容器 | `st.tabs(["列表", "新增", "匯入"])` | 三分頁 |
| 篩選列 | `st.columns` + `st.selectbox`(分類:全部/感測器/系統/應用/網路)+ `st.date_input`(時間範圍,`value=(起, 迄)`)+ `st.text_input`(關鍵字) | 送出可用 `st.button` 或 `on_change` 觸發查詢 |
| 資料表 | `st.dataframe` | `column_config` 格式化欄位、`hide_index=True`、欄位點擊排序;可選 `on_select="rerun"` + `selection_mode` 支援選列 |
| 逐列動作 | 每列 `st.columns` + `st.button("編輯")` / `st.button("刪除")` | 非創建者且非 Admin → `disabled=True`(停用不隱藏) |
| 分頁列 | `st.columns` + `st.button("‹ 上一頁")` / `st.button("下一頁 ›")` + `st.caption("第 N / M 頁")` | 頁碼存 `st.session_state`,轉為 API `page`/`size` |
| 新增表單 | `st.form("create")` + `st.text_input` + `st.number_input` + `st.selectbox` + `st.form_submit_button("送出")` | `clear_on_submit=True` |
| 編輯彈窗 | `@st.dialog("編輯資料")` 內 `st.form` | 載入既有值為預設 |
| 刪除確認 | `@st.dialog("確認刪除")` + `st.button("確認刪除", type="primary")` + `st.button("取消")` | 二次確認,危險色 |
| 匯入上傳 | `st.file_uploader("CSV / JSON", type=["csv","json"])` | 單檔;大檔提示 |
| 匯入預覽 | `st.dataframe`(前 N 列)+ 欄位對應提示 + 錯誤列標示 | pandas 解析 |
| 匯入送出 | `st.button("確認匯入")` + `st.progress` / `st.spinner` | 批量寫入進度 |
| 操作回饋 | `st.toast` / `st.success` / `st.error` / `st.spinner` | 成功/失敗/載入中 |
| 空狀態 | `st.info` / `st.empty` | 查無資料時取代表格 |

---

## 分頁一:列表(讀取 / 更新入口 / 刪除入口)

### 版面

```
── 列表 ──────────────────────────────────────────────────────
 分類[▾ 全部]  期間[起]–[迄]  關鍵字[__________]   [ 篩選 ]     ← st.columns([1,2,2,1]) 篩選列
──────────────────────────────────────────────────────────────
 ┌──────────────────────────────────────────────────────────┐
 │ 標題      數值    分類    創建者   建立時間   [編輯][刪除] │  ← st.dataframe + 逐列動作
 │ 溫度異常  87.2   感測器   alice   07-18 10:02  [✎][🗑]    │     動作依權限 disabled
 │ …                                                          │
 └──────────────────────────────────────────────────────────┘
 每頁 [20 ▾] 筆        ‹ 上一頁    第 3 / 20 頁    下一頁 ›     ← 分頁列(後端 page/size)
```

### 元件細節

- **篩選**:分類 `st.selectbox`(含「全部」)、時間範圍 `st.date_input`(tuple 起迄)、關鍵字 `st.text_input`(比對標題)。按「篩選」或 `on_change` 重查,篩選條件存 `st.session_state` 以跨 rerun 保留。
- **表格**:`st.dataframe` + `column_config`(數值靠右、時間格式化、分類可用 `TextColumn`),點欄位標題排序;排序欄與方向轉為 API 查詢參數。
- **逐列動作**:每列「編輯」「刪除」按鈕。權限判斷在 Python 端(`row.created_by == current_user or is_admin`),無權限 `disabled=True`。
- **分頁**:每頁筆數 `st.selectbox`(20/50/100),上一頁/下一頁 `st.button`,頁碼 `st.caption`。**由後端分頁**,前端只傳 `page` / `size`,避免全量載入。

### 編輯(更新)

- 點「編輯」開 `@st.dialog`,內含 `st.form`,欄位預填既有值 → 修改 → `st.form_submit_button("更新")` → 呼叫更新 API。
- 權限:創建者或 Admin(前端停用按鈕,後端亦強制)。
- 成功 → `st.toast("已更新")` + 關閉彈窗 + `st.rerun()` 刷新列表。

### 刪除

- 點「刪除」開 `@st.dialog` 二次確認,顯示該筆摘要(標題)。
- 「確認刪除」用 danger 色(`type="primary"` + CSS)、另有「取消」。
- 建議軟刪除保留稽核;成功 → `st.toast` + 刷新。

---

## 分頁二:新增(建立)

```
── 新增 ──────────────────────────────────────────────────────
 標題    [________________________]                           ← st.text_input(必填)
 數值    [__________]     分類 [▾ 感測器]                       ← st.number_input(float) + st.selectbox
 備註    [________________________]  (可選)                    ← st.text_area(可選)
                                             [ 送出 ]          ← st.form_submit_button
```

- 以 `st.form("create", clear_on_submit=True)` 包裹,避免逐欄 rerun。
- 欄位(對應 `Record`):標題(`st.text_input`,必填非空)、數值(`st.number_input`,float)、分類(`st.selectbox`,選項=`感測器/系統/應用/網路`)、備註(`st.text_area`,可選,對應 `note`)。
- **`id` / `created_by` / 時間戳由來源端自動帶入**,前端不填(`created_by` 取自目前 Actor)。
- 送出前做前端基本驗證(必填、數值可解析);失敗以 `st.error` 提示且不送出;來源端二次驗證失敗回 `ValidationError`。
- 成功 → `st.success` / `st.toast` + 清空表單;可選跳「列表」分頁。

---

## 分頁三:匯入(批量建立)

```
── 匯入 ──────────────────────────────────────────────────────
 [ ⬆ 拖曳或選擇 CSV / JSON ]                                   ← st.file_uploader
 範本下載: [ CSV 範本 ] [ JSON 範本 ]                          ← st.download_button(可選)
──────────────────────────────────────────────────────────────
 預覽(前 20 列):
 ┌────────────────────────────────────────────┐
 │ 標題   數值   分類    ← 欄位對應             │  ← st.dataframe,錯誤列以 danger 標示
 │ …                                            │
 └────────────────────────────────────────────┘
 通過 18 列 / 錯誤 2 列                          ← st.metric 或 st.caption
                                   [ 確認匯入 ]  ← st.button + st.progress
```

- `st.file_uploader` 接受 `csv` / `json`(單檔),以 pandas 解析。
- **預覽**:`st.dataframe` 顯示前 N 列 + 欄位對應;逐列驗證必填/型別。
- **錯誤處理**:錯誤列以 danger 色標示並列出原因,**不中斷其餘**;顯示「通過 X / 錯誤 Y」統計。
- 「確認匯入」→ 批量送後端建立 API,`st.progress` / `st.spinner` 顯示進度,完成回報成功/失敗筆數。
- 可選:提供 CSV / JSON 範本 `st.download_button`。

---

## 權限規則

| 動作 | 允許者 | 前端呈現 |
|---|---|---|
| 讀取 | 所有登入者 | 一律可用 |
| 建立 / 批量匯入 | 所有登入者 | 一律可用 |
| 更新 / 刪除 | 該筆創建者、Admin | 無權限 → 按鈕 `disabled=True`(停用不隱藏) |

- 權限判斷用純函式 `can_edit(record, actor)`(Admin 恆真;否則需為創建者)決定按鈕 `disabled`;**後端 API 亦強制驗證**,前端控制僅為體驗。
- `actor` 取自 `st.session_state["actor"]`:mock 由開發切換器提供,正式由認證(見 [ADR 0003](../decisions/0003-auth-via-bff-token-exchange.md))提供。

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
| 查無資料 | `st.info` 空狀態,取代表格 |
| 建立/更新/刪除成功 | `st.toast` / `st.success` + 刷新 |
| 來源失敗 / 逾時 | `st.error`,保留頁面框架,可重試(mock 階段不會發生) |
| 無權限操作 | 按鈕停用 + 提示;來源拋 `PermissionDenied`(對應 403)亦以 `st.error` 呈現 |
| 找不到資料 | `RecordNotFound`(對應 404)→ `st.error` 並刷新列表 |
| 建立/更新欄位不合法 | `ValidationError`(對應 422)→ 表單旁 `st.error` |
| 匯入格式錯誤 | 標示問題列,不中斷其餘 |

---

## 樣式對照(設計 Token)

| 用途 | Token | 說明 |
|---|---|---|
| 主要按鈕 / 送出 | primary `#2563eb` | 新增、確認匯入 |
| 刪除 / 錯誤列 | danger `#dc2626` | 刪除確認、匯入錯誤列 |
| 成功提示 | success `#16a34a` | toast / success |
| 區塊底色 | secondaryBackground `#f1f5f9` | 卡片 / 篩選列容器 |

- 顏色一律走主題 token,不散寫魔術數字;需狙擊容器用 `st.container(key=...)`。

---

## 效能與依賴 / 備註

- **分頁 / 篩選 / 排序在來源端**:頁面只傳 `page` / `size` / `category` / `keyword` / `sort` 給 `DataSource`,mock 於記憶體處理、日後由後端 API 處理,避免全量載入前端。
- 讀取類查詢可用 `st.cache_data` 設短 TTL(mock 階段可略);寫入後主動清快取或 `st.rerun()`。
- 大量匯入分批送出,避免單次請求過大;mock 上限單檔 1000 列。

---

## 可測試性(對齊 TDD)

- 純邏輯抽到 `lib/`(不依賴 Streamlit):`can_edit(record, actor)`、`MockDataSource` 的分頁/篩選/排序/CRUD、匯入解析與驗證 → `tests/unit/`。
- 頁面行為以 `AppTest` 覆蓋:切換使用者後按鈕停用、分頁切換、匯入錯誤列標示、送出後刷新 → `tests/app/`。
- 完整行為切分與 RED 順序見[資料來源規格「對齊 TDD 的落地順序」](../data-source.md#對齊-tdd-的落地順序)。
