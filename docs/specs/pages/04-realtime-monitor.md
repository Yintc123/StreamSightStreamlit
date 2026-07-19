# 頁面規格：即時監控（串流資料）

- 頁面編號：4
- 對應檔案：`pages/realtime_monitor.py`
- 純邏輯模組：`lib/realtime.py`
- 存取權限：**已登入使用者**（無角色 gate；未登入由 `app.py` 導向 Next.js 登入頁）
- 資料來源：
  - **目前（mock 先行）**：前端本地「模擬即時資料生成器」，每秒生成一個決定性隨機值（見 [ADR 0002](../../decisions/0002-streamlit-as-api-client.md) 的 mock 先行原則）。
  - **未來（接後端）**：改由 FastAPI WebSocket 推送即時串流（見 [ADR 0001](../../decisions/0001-realtime-architecture.md)）；`lib/realtime.py` 的純函式與頁面版面不變，只替換「取值來源」。
- 相關：[UI Helper 規格](../ui.md)、[錯誤處理規格](../error-handling.md)、[前端頁面結構](../frontend-pages.md)、[應用骨架 §5/§7](../app-skeleton.md)

> **設計變更說明**：本頁原規劃為「DB 主機資源監控（僅 Admin、mock 停用）」。經需求調整，改為**通用單串流即時監控**：模擬即時資料流、折線 / 柱狀圖即時更新、數值超過閾值時告警，**mock 模式即可完整呈現**、所有登入者可見。DB 資源監控如日後需要，另立頁面或分頁，不併入本頁。

---

## 目的

以最小依賴示範「即時資料監控」：

1. **模擬即時資料生成器** — 每秒生成一個隨機數值（0–100）。
2. **即時推送 / 刷新** — mock 階段以 `st.fragment(run_every=1.0)` 每秒重繪；接後端後改為 WebSocket 推送。
3. **即時圖表更新** — 折線圖顯示趨勢、柱狀圖顯示近況快照。
4. **數值異常告警** — 目前值超過可調閾值時，於指標卡（inverse delta）與 `st.toast` overlay 標記（不佔版面）。

---

## UI 版面規劃

寬版單欄，由上而下：閾值控制 → 即時指標列 → 折線圖 → 柱狀圖。**告警不佔版面**——以 `st.toast` overlay 呈現（見下），故超標與否都不會推移圖表位置。

```
┌──────────────────────────────────────────────────────────────┐
│ 即時監控                              最後更新 12:00:03        │ ← st.title + 右側 caption
│ 模擬即時資料串流（每秒更新）。數值超過閾值時告警。            │ ← st.caption 說明
├──────────────────────────────────────────────────────────────┤
│ 告警閾值  [────────●───] 80                                   │ ← st.slider（0–100）
├──────────┬──────────┬──────────┬────────────────────────────┤
│ 目前值    │ 近60筆最大│ 近60筆平均│ 超標筆數                    │ ← metric_cards(4 個 Metric)
│  45.2    │  91.7    │  52.3    │   3 ⚠                       │   （超標時「目前值」卡帶 delta 並轉 inverse）
├──────────────────────────────────────────────────────────────┤   ┌─ ⚠️ 告警：目前值 91.7 已超過閾值 80 ─┐
│ 趨勢（近 60 筆）                                              │   └─ st.toast overlay（右下角，不佔版面）─┘
│      ▁▂▃▄▃▂▁▂▃▄▅▄▃▂▃▄▅▆▅▄▃▂▃▄▅                              │ ← st.altair_chart（x 軸刻度 12:00:03 / y「數值」）
│   12:00:05   12:00:15   12:00:25   12:00:35                   │   x 軸刻度以 %H:%M:%S 明確顯示時:分:秒
├──────────────────────────────────────────────────────────────┤
│ 近況（最近 15 筆）                                            │ ← st.altair_chart（bar，同上軸格式）
│      ▃▅▂▆▄▃▇▅▂▄▆▃▅▄▂                                        │
└──────────────────────────────────────────────────────────────┘
```

| 區域 | 元件 | 備註 |
|---|---|---|
| 閾值控制 | `st.slider("告警閾值", 0, 100, 80, key="rt_threshold")` | 使用者可調；改變即時反映於告警判斷 |
| 即時指標列 | `metric_cards(summary_metrics(...))` | 4 個 `Metric`；目前值超標時帶 `delta`（超出量）＋ `delta_color="inverse"` |
| 告警 | `st.toast(alert_message(...), icon="⚠️")` | 僅當「目前值 > 閾值」時觸發；**overlay 不佔版面**，圖表不因告警出現/消失而位移。持續性視覺信號由「目前值」卡的 inverse delta 承擔 |
| 趨勢折線圖 | `st.altair_chart(build_chart(buffer, "line"), use_container_width=True)` | 單線；x 軸 temporal，刻度以 `%H:%M:%S` 明確顯示時:分:秒；最多 `MAX_POINTS`（60）筆 |
| 近況柱狀圖 | `st.altair_chart(build_chart(buffer[-RECENT_POINTS:], "bar"), use_container_width=True)` | 最近 `RECENT_POINTS`（15）筆長條；同 x 軸時間格式 |
| 最後更新時間 | `st.caption` | 顯示最新一筆 `ts` 的本地時間 |
| 空緩衝 | `empty_state("資料串流啟動中…")` | 首次進入、緩衝為空時取代圖表 |

---

## 功能細節

### 存取控制

本頁對所有登入者開放，**不需頁內角色 gate**。未登入的導向已由 `app.py`（meta refresh 跳轉 Next.js）處理，頁面內不再重複判斷。

### 即時刷新（mock 階段）

以 `st.fragment(run_every=1.0)` 包住「取值 → 更新緩衝 → 繪圖」區塊，Streamlit 每秒只重跑該 fragment（非整頁），無第三方 auto-refresh 依賴。

**元件邊界（fragment 內／外）——單一真相**：fragment `run_every` 只會每秒重繪 **fragment 內**的元件；放在外面的東西不會每秒更新。故：

| 位置 | 元件 | 理由 |
|---|---|---|
| **fragment 外**（頁面進入時執行一次） | `st.title`、說明 `st.caption`、閾值 `st.slider(key="rt_threshold")`、`rt_buffer`/`rt_tick` 初始化 | 靜態版面 / 使用者輸入；slider 值經 session_state 讀入 fragment |
| **fragment 內**（每秒重繪） | 「最後更新」caption、指標卡、告警 `st.toast`、折線圖、柱狀圖 | 皆需隨新值刷新——**「最後更新」caption 必須在 fragment 內**，否則時間戳不會走動 |

> **版面註**：fragment 內元件渲染於「呼叫 `live_panel()` 之處」，即靜態標題列**下方**。故上方 ASCII 將「最後更新」畫在標題右側僅為位置示意；實作上它出現在 live panel 頂端。若確需與標題同列右對齊，須把標題列一併納入 fragment（本規格不要求，維持標題靜態）。

**先在 fragment 之外初始化 session_state**，否則首幀讀 `rt_buffer` / `rt_tick` 會 `KeyError`：

```python
# 頁面進入時、fragment 之外——初始化契約（見 §session_state 契約）
st.session_state.setdefault("rt_buffer", [])
st.session_state.setdefault("rt_tick", 0)
# rt_threshold 由 slider key="rt_threshold" 自動建立，不在此初始化

@st.fragment(run_every=1.0)
def live_panel():
    # ── 1) 繪圖：依「當前緩衝」渲染（先渲染、後生成，見下方執行序註）──
    buffer = st.session_state["rt_buffer"]
    threshold = st.session_state.get("rt_threshold", int(DEFAULT_THRESHOLD))
    if not buffer:                                  # 冷啟首幀＝真正「串流啟動中…」
        empty_state("資料串流啟動中…")
    else:
        st.caption(f"最後更新 {buffer[-1].ts.strftime('%H:%M:%S')}")   # fragment 內
        metric_cards(summary_metrics(buffer, threshold))
        if is_over(buffer[-1].value, threshold):
            st.toast(alert_message(buffer[-1].value, threshold), icon="⚠️")  # overlay，不佔版面
        st.altair_chart(build_chart(buffer, "line"), use_container_width=True)                 # x 軸時:分:秒
        st.altair_chart(build_chart(buffer[-RECENT_POINTS:], "bar"), use_container_width=True)
    # ── 2) 生成下一筆餵「下一幀」：讀 tick → sample → append → tick+=1 ──
    #     mock 專屬；接後端後此段由 WS 推送 callback 填 rt_buffer 取代，第 1 段不變。
    tick = st.session_state["rt_tick"]
    reading = Reading(ts=datetime.now().astimezone(), value=sample_value(tick))
    st.session_state["rt_buffer"] = trim(buffer + [reading], MAX_POINTS)
    st.session_state["rt_tick"] = tick + 1          # 首幀 tick=0，之後遞增
```

- **執行序（render-then-sample，釘死）**：**先**依當前緩衝繪圖，**再**生成下一筆餵下一幀。理由：
  1. **empty_state 真實可達且語意正確**——冷啟首幀緩衝為空 → 顯示「資料串流啟動中…」，第二幀起有資料；非「靠 stub 才會出現的死路徑」。
  2. **與接後端架構一致**——WS 模型本就是「資料非同步到達緩衝、fragment 只渲染當前緩衝」；改接後端時**只移除第 2 段**（改由 WS callback 填 `rt_buffer`），第 1 段渲染邏輯一字不改。
  - 代價：新生成值於「下一幀」（約 1 秒後）才顯示——對每秒刷新的即時監控無感，且與 WS 的到達延遲同性質。
- **tick 遞增（釘死）**：`讀 tick → sample_value(tick) → append → rt_tick += 1`；首幀 `tick=0`，`(session, tick)` 與所取值一一對應、可重現。
- **不使用** `time.sleep(...) + st.rerun()`：該寫法會讓 `AppTest` 陷入無限迴圈，且會重跑整頁。`st.fragment(run_every=...)` 在 `AppTest` 下只執行首幀、不自動循環，可測。

### 模擬即時資料生成器

值由 `lib/realtime.py::sample_value(tick, seed)` 產生，**決定性**（同 `(tick, seed)` → 同值），避免使用 `datetime.now()` / 全域 `random`，以利單元測試：

```python
from lib.realtime import sample_value

tick = st.session_state["rt_tick"]
value = sample_value(tick)          # 0–100，一位小數
```

- **tick 遞增時機（釘死）**：`讀 tick → sample_value(tick) → append → rt_tick += 1`。首幀用 `tick=0`，之後每次 fragment 執行 +1；遞增在 sample **之後**，故 `(session, tick)` 與所取值一一對應、可重現（見 §即時刷新 pseudocode）。
- 時間戳 `ts` 於頁面以真實時鐘（`datetime.now().astimezone()`＝**本地時區 aware**）標記後存入緩衝——直接存本地時間，caption 顯示時無需再轉換；時間戳屬「當下呈現」，不進純函式，故不影響可測性。接後端後若 WS 送 UTC，於消費層轉本地。

### 緩衝（環形）

歷史值存於 `st.session_state["rt_buffer"]`（`List[Reading]`），以 `trim(buffer, MAX_POINTS)` 保留最近 `MAX_POINTS`（60）筆。折線圖用整段緩衝、柱狀圖用最近 `RECENT_POINTS`（15）筆——兩個視窗大小由 `lib/realtime.py` **具名常數單一來源**（見 §純函式契約），頁面 import 使用，不散寫魔術數字：

```python
from lib.realtime import MAX_POINTS, RECENT_POINTS, Reading, trim

reading = Reading(ts=datetime.now().astimezone(), value=value)   # 本地時區 aware
st.session_state["rt_buffer"] = trim(
    st.session_state["rt_buffer"] + [reading], MAX_POINTS
)
```

### 即時指標列

以 `summary_metrics(buffer, threshold)` 依緩衝計算 4 個 `Metric`（重用 [UI Helper §4](../ui.md#4-metric_cards--指標卡列) 的 `Metric` / `metric_cards`）：

| 指標 | 值 | `delta` / `delta_color` 規則 |
|---|---|---|
| 目前值 | 最新一筆 value | 超標（value > 閾值）→ `delta=round(value - threshold, 1)`（超出量，正數）＋ `delta_color="inverse"`；否則 `delta=None`、`delta_color="off"` |
| 近 60 筆最大 | `max(values)` | 無 `delta`（`delta_color` 維持預設，不塗色） |
| 近 60 筆平均 | `mean(values)`（四捨五入 1 位） | 無 `delta`（同上） |
| 超標筆數（近 60 筆） | 緩衝內 value > 閾值 的筆數 | 無 `delta`；視覺信號交給 `st.toast` 告警與「目前值」卡（見下方註） |

> **為何超標時「目前值」一定要給 `delta`**：Streamlit 的 `st.metric` 在 `delta=None` 時會**忽略** `delta_color`，既不上色也不顯示。要讓 inverse 生效，必須同時提供 `delta`，故超標時以「超出量」作為 `delta`。其餘卡片不硬塗色，避免設了不會顯示的 no-op。
> **命名與時間窗**：緩衝是 **count-based（最近 `MAX_POINTS`＝60 筆）**，故一律以「近 60 筆」描述，不寫「近 60 秒」（純函式只知筆數、不保證秒數，掉幀時兩者不等）。標籤中的「60」由 `MAX_POINTS` 導出，改常數即同步。**暖機期**（緩衝未滿 60 筆）標籤仍寫「近 60 筆」但實際統計筆數較少——此為刻意接受的近似（純函式只知當前筆數）。「超標筆數」是當前緩衝內超標的**即時計數**，會隨緩衝滾動與閾值調整而變，非累計告警數。

- 緩衝為空時 `summary_metrics` 回空 list（`metric_cards` 對空 list 靜默），改由 `empty_state()` 呈現。

### 告警

- **目前值 > 閾值** 時，以 `st.toast(alert_message(value, threshold), icon="⚠️")` 觸發 overlay 告警，並使「目前值」指標卡帶 `delta`（超出量）＋ `delta_color="inverse"`（無 `delta` 時 `delta_color` 不生效，見 §即時指標列註）。
- **為何用 toast 而非 `st.error`**：`st.error` 是版面內元件，超標時插入、回落時消失，會使下方兩張圖表反覆上下位移；`st.toast` 為右下角 overlay，**不佔版面**，圖表位置恆定。持續性視覺信號改由「目前值」卡的 inverse delta 承擔（toast 為短暫提示、卡片為常駐狀態）。
- 判斷邏輯為純函式 `is_over(value, threshold)`、文案為純函式 `alert_message(value, threshold)`（見下）；頁面只做呈現。
- **刷新頻率註**：`run_every=1.0` 下持續超標會每秒觸發一次 toast。此為刻意取捨（transient 提示不佔版面）；常駐狀態看指標卡。若日後需抑制連續 toast，可於 session_state 記錄前一幀是否超標，僅在「未超標 → 超標」的跨越邊界觸發。

---

## `lib/realtime.py` 純函式契約（單一真相）

所有函式**無 Streamlit 依賴**，可直接單元測試。型別以相容 Python 3.9 寫法（`from __future__ import annotations`）。

```python
CHANNEL = "數值"          # DataFrame 欄名 / 圖表圖例
DEFAULT_THRESHOLD = 80.0
VALUE_MIN, VALUE_MAX = 0.0, 100.0
MAX_POINTS = 60           # 環形緩衝上限＝折線圖視窗（trim 用；指標卡「近 N 筆」的 N）
RECENT_POINTS = 15        # 柱狀圖「近況」視窗（buffer[-RECENT_POINTS:]）
X_AXIS_LABEL = "時間（時:分:秒）"   # 折線 / 柱狀圖 x 軸中文標籤（含單位）
Y_AXIS_LABEL = "數值（0–100）"      # 折線 / 柱狀圖 y 軸中文標籤（含值域）
TIME_FORMAT = "%H:%M:%S"           # x 軸刻度時間格式（d3-time-format；明確顯示時:分:秒）

@dataclass
class Reading:
    ts: datetime          # 產生當下時間（頁面以 datetime.now().astimezone() 標本地時區 aware）
    value: float          # 0–100，一位小數

@dataclass
class Alert:
    value: float
    threshold: float
```

| 函式 | 簽章 | 契約 |
|---|---|---|
| `sample_value` | `(tick: int, seed: int = 0) -> float` | 決定性：同 `(tick, seed)` → 同一值；落在 `[0, 100]`，四捨五入 1 位。不同 tick 一般不同。 |
| `generate_stream` | `(n: int, start_tick: int = 0, seed: int = 0) -> List[float]` | 連續 `n` 個 `sample_value`；`len == n`；決定性。 |
| `is_over` | `(value: float, threshold: float) -> bool` | `value > threshold`（嚴格大於）。 |
| `alert_message` | `(value: float, threshold: float) -> str` | 告警文案；**不含前導警示符號**（圖示交由 `st.toast(icon="⚠️")`）；含 value 與 threshold。 |
| `readings_to_df` | `(readings: List[Reading]) -> pd.DataFrame` | index=`ts`（DatetimeIndex，由舊到新排序）、單欄 `CHANNEL`；空 list → 空 DataFrame（欄含 `CHANNEL`）。（DataFrame 工具函式；圖表改由 `build_chart` 建構。） |
| `build_chart` | `(readings: List[Reading], mark: str = "line") -> alt.Chart` | 回傳 Altair 圖表；x 軸 temporal 且刻度 `format=TIME_FORMAT`（明確時:分:秒）、軸標題為 `X_AXIS_LABEL` / `Y_AXIS_LABEL`；`mark="line"`（趨勢）/ `"bar"`（近況）；內部欄名 ASCII（`ts`/`value`）避免 Altair shorthand 解析中文；空 list 不拋例外。 |
| `summary_metrics` | `(readings: List[Reading], threshold: float) -> List[Metric]` | 回傳 4 個 `Metric`（目前 / 近 N 筆最大 / 近 N 筆平均 / 超標筆數，`N = MAX_POINTS`，標籤字串由 `MAX_POINTS` 導出以單一來源）；空 list → `[]`（不拋例外）；目前值 > 閾值時「目前值」卡 `delta=round(value-threshold, 1)`＋`delta_color="inverse"`，否則 `delta=None`、`delta_color="off"`。 |
| `trim` | `(buffer: List[Reading], max_len: int) -> List[Reading]` | 回傳最後 `max_len` 筆（`max_len >= 0`）；不足則原樣回傳；不變更輸入。 |

> `Metric` 由 `lib/ui.py` import 重用，不另定義。

---

## Mock 模式行為（`DATA_SOURCE=mock`）

**完全可用**——本頁的即時值由前端生成器產生，不依賴後端，故 mock 模式即為主要展示模式：

- 正常每秒刷新、繪圖、告警。
- 不需 `st.stop()`，不需 API 連線。
- `DATA_SOURCE=api`（接後端後）時，改由 WebSocket 取值；若連線失敗，依「狀態與錯誤處理」呈現並**停止刷新**。

---

## 資料

- 唯讀頁面，不做寫入、不落 DB。
- mock 階段歷史值只存於 `st.session_state`（每連線 / 每分頁獨立），保留最近 60 筆，隨頁面關閉即釋放。
- 前端不直接連 DB / Redis；接後端後一律透過 WebSocket / `ApiClient`（見 [ADR 0002](../../decisions/0002-streamlit-as-api-client.md)）。

---

## session_state 契約

使用 `rt_` 前綴（見[應用骨架 §7](../app-skeleton.md#7-session_state-契約單一真相)）：

| Key | 型別 | 說明 |
|---|---|---|
| `rt_buffer` | `List[Reading]` | 環形緩衝，最近 60 筆即時值；每秒 append + `trim`。 |
| `rt_tick` | `int` | 生成器計數器，決定 `sample_value` 取哪一筆；每次刷新 +1。 |
| `rt_threshold` | `int` | 告警閾值 slider 綁定值（0–100，預設 80）；由 slider `key="rt_threshold"` 自動建立，不需手動初始化。**僅本次 session 記憶**——重整 / 重開即回預設 80（見下方持久化註）。 |
| `rt_last_error` | `Optional[str]` | 接後端後：最近一次 WebSocket / API 失敗訊息，用於停止刷新（mock 階段不使用）。 |

> **初始化契約**：`rt_buffer`（`[]`）與 `rt_tick`（`0`）於**頁面進入時、fragment 之外**以 `st.session_state.setdefault(...)` 建立，避免首幀 `KeyError`（見 §即時刷新）；`rt_threshold` 由 slider 自動建立，無需手動初始化。
> **型別註**：`rt_threshold` 由 slider 綁定為 `int`；純函式一律以 `float` 運算（`DEFAULT_THRESHOLD = 80.0`），`int` 與 `float` 在 Python 比較無礙，故不需顯式轉型。
> **持久化（延後）**：閾值目前**僅存於 `session_state`（單一 session 記憶）**，不跨重整 / 重開保留。此階段為 mock 先行、無後端，跨 session 持久化的正統位置是**後端使用者偏好**（前端為 API Client，不自持狀態）；後端偏好端點尚未就緒，故先維持 session-only，延後至接後端 cycle 再永久化。

---

## 狀態與錯誤處理

依 [錯誤處理規格 §3](../error-handling.md#3-呈現契約本規格唯一權威)：

| 情境 | 呈現 |
|---|---|
| 緩衝為空 | `empty_state("資料串流啟動中…")` 取代圖表；不渲染指標卡 |
| 目前值 > 閾值 | `st.toast(alert_message(...), icon="⚠️")`（overlay，不佔版面）+ 「目前值」卡帶 `delta`（超出量）＋ `delta_color="inverse"` |
| 目前值 ≤ 閾值 | 不觸發 toast；「目前值」卡 `delta=None`、`delta_color="off"` |
| （接後端後）WebSocket / API 失敗 | `render_error(exc)` + 保留頁面框架 + **停止刷新**（不再 `run_every`） |

- **「緩衝為空」何時出現**：因 render 早於 sample（render-then-sample，見 §即時刷新執行序），**冷啟首幀緩衝為空 → 顯示「資料串流啟動中…」**，第二幀（約 1 秒後）起有資料轉為圖表。此列於 mock 與接後端 cycle（WS 未收到第一筆）**語意一致**，且 empty_state 為首幀天然可達路徑（測試 15，無需 stub）。
- mock 階段無「API 失敗」情境；該列於接後端 cycle 才生效。

---

## lib/ 依賴

| 模組 | 用途 |
|---|---|
| `lib/realtime.py` | 生成器 / 告警文案 / DataFrame / Altair 圖表建構（`build_chart`）/ 指標卡計算（本頁純邏輯，新增） |
| `altair` | `build_chart` 建構折線 / 柱狀圖，x 軸刻度格式化為 `%H:%M:%S`（Streamlit 既有相依） |
| `lib/ui.py` | `Metric`、`metric_cards`、`empty_state`（重用） |
| `lib/errors.py` | `render_error`（接後端後的失敗呈現） |
| `lib/config.py` | 判斷 `data_source`（mock / api）決定取值來源（接後端後） |

> 本頁 mock 階段**不**依賴 `lib/api_client.py` 與 `lib/state.py`（無角色 gate）。接後端後才引入 WebSocket client。

---

## 可重用元件盤點

| 元件 | 來源 | 用途 | 是否需改 |
|---|---|---|---|
| `Metric` / `metric_cards()` | `lib/ui.py` | 即時指標列 | 直接用 |
| `empty_state()` | `lib/ui.py` | 空緩衝呈現 | 直接用 |
| `render_error()` | `lib/errors.py` | 接後端後失敗呈現 | 直接用 |
| `st.fragment(run_every=...)` 模式 | Streamlit 內建 | 即時刷新，無第三方依賴 | 本頁即時刷新採用 |
| `st.altair_chart` + Altair | Streamlit 內建整合（Altair 為既有相依） | 折線 / 柱狀圖，x 軸刻度可指定 `%H:%M:%S` | 由 `build_chart` 建構（`st.line_chart` 無法指定刻度時間格式，故改用） |
| `rt_` session_state 前綴 | 本規格 §session_state | 緩衝 / tick / 閾值 | 沿用命名 |
| nav 註冊（「即時監控」給所有登入者） | `lib/nav.py::build_pages` | 頁面已註冊 | **不用改** |

> `lib/analytics.py` 的純函式綁 `Record`/`created_at` 資料形狀，**不直接重用**；`readings_to_df` 照其 `records_to_df` 的 DataFrame-index 風格撰寫以維持一致。

---

## 可測試性 / TDD

> **關鍵限制**：`st.fragment(run_every=1.0)` 的自動刷新在 `AppTest` 下只執行首幀、不自動循環，故可測首幀行為；**不測自動刷新本身**。所有數值 / 告警 / DataFrame 邏輯抽為 `lib/realtime.py` 純函式，於 unit 層完整覆蓋。

### 純函式（`tests/unit/test_realtime.py`）

1. `sample_value(tick)` 決定性：`sample_value(5) == sample_value(5)`。
2. `sample_value(tick)` 落在 `[0, 100]`（掃多個 tick）。
3. `sample_value` 對不同 tick 至少產生兩種不同值（非常數）。
4. `generate_stream(n)` 長度為 `n`、決定性、每個元素落在 `[0, 100]`。
5. `is_over(90, 80) is True`；`is_over(80, 80) is False`（嚴格大於）。
6. `readings_to_df([])` → 空 DataFrame，欄含 `CHANNEL`。
7. `readings_to_df(readings)` → index 為 DatetimeIndex、由舊到新排序、單欄 `CHANNEL`。
8. `summary_metrics([], 80)` → `[]`（不拋例外）。
9. `summary_metrics(readings, 80)` → 4 個 `Metric`，值對應 目前 / 近60筆最大 / 近60筆平均 / 超標筆數。
10. 最新值 > 閾值 → 「目前值」`Metric.delta` 非 `None`（等於超出量 `round(value-threshold, 1)`）且 `delta_color == "inverse"`；≤ 閾值 → `delta is None` 且 `delta_color == "off"`。
11. `trim(buffer, 60)`：長度 70 → 回傳最後 60 筆；長度 30 → 原樣回傳；不變更輸入。
12. `alert_message(value, threshold)`：含 value 與 threshold，**不以警示符號起首**（圖示交由 `st.toast`）。
13. `X_AXIS_LABEL` / `Y_AXIS_LABEL` 為中文含單位軸標籤（單一來源，供頁面 import）。
13a. `build_chart(readings, "line"/"bar")`（以 `.to_dict()` 驗證）：x 軸 `type=="temporal"` 且 `axis.format=="%H:%M:%S"`、x/y 軸標題等於 `X_AXIS_LABEL`/`Y_AXIS_LABEL`、`mark.type` 對應 line/bar；空 readings 不拋例外。

### 頁面行為（`tests/app/test_realtime_monitor.py`，AppTest）

> 以下 AppTest 均採 render-then-sample 執行序（見 §即時刷新）：首幀渲染依「進入該幀時的 `rt_buffer`」，故**注入 `rt_buffer` 即可決定首幀畫面**，無需 monkeypatch 生成器。閾值以注入 `rt_threshold` 控制（slider 在 fragment 外、值經 session_state 讀入）。

14. 登入使用者（admin，任一 grade，例如 `grade=0`（viewer））進入（session_state **未預設** `rt_buffer` / `rt_tick`）→ 頁面含「即時監控」標題，無 exception（驗證初始化契約，不觸發 `KeyError`；本頁對所有 grade 開放，viewer=0 亦可讀）。
15. **注入** `rt_buffer=[Reading(now, 42.0)]`（首幀即有資料）→ 含 `st.metric`（指標卡）與閾值 `st.slider`。
16. **告警可判定**：注入 `rt_buffer=[Reading(now, 50.0)]` ＋ `rt_threshold=10` → `is_over(50.0, 10)` 必為真 → 首幀渲染含 `st.toast`（告警），且**無** `st.error`（告警不佔版面）。以「注入已知值 + 低閾值」使斷言 100% 可判定；**不靠**「閾值設 0」——`is_over` 為嚴格 `>`、值域含 `0.0`，設 0 無法保證超標。
17. **未預設 / 空 `rt_buffer`**（首幀緩衝為空）→ 首幀渲染含 `st.info`（empty_state），不渲染指標卡。render-then-sample 使冷啟首幀天然為空，empty_state **無需 stub 即可測**（見 §狀態與錯誤處理）。

> 依 CLAUDE.md：逐一先寫失敗測試 → 最小實作 → 綠燈重構。先做 `lib/realtime.py`（unit 1–13），再做頁面（AppTest 14–17）。

---

## 依賴

- Streamlit 端**無新增第三方依賴**（`pandas` / `altair` 均為 Streamlit 既有相依；`st.fragment` / `st.altair_chart` 為內建）。
- 接後端 cycle 才需要：FastAPI WebSocket 端點、`lib/` WebSocket client。

---

## 接後端 WS Cycle（DATA_SOURCE=api）

> **狀態：待實作**。對齊後端規格 [`realtime-stream.md`](../../../../StreamSightBackend/docs/specs/realtime-stream.md)（`RealtimeStreamer` task，`realtime.stream` topic，ticket 認證）。後端先達 Green，前端此節緊接實作。

### 概覽

mock 階段 `live_panel()` 第 2 段（每幀 `sample_value`）以 **`RealtimeWsClient`**（daemon thread + asyncio loop）取代。`live_panel()` 第 1 段（渲染邏輯）**完全不變**——仍讀 `st.session_state["rt_buffer"]`，差異只在「資料從哪來」。

**三個改動（合計約 60 行）**：

| 檔案 | 動作 |
|---|---|
| `lib/realtime_ws.py` | **新增**；WS client 純 Python（daemon thread + asyncio loop + threading.Lock）|
| `lib/config.py` | 新增 `fastapi_ws_url` property（`http→ws`、`https→wss`）|
| `pages/realtime_monitor.py` | 初始化 `RealtimeWsClient`；`live_panel()` 移除第 2 段；改讀 `ws.buffer` |

---

### 資料流（接後端端到端）

```
FastAPI lifespan
  └── RealtimeStreamer（每秒）
        ├── Redis INCR "realtime:tick"
        ├── sample_value(tick) → float
        └── Publisher.to_topic("realtime.stream", {type, topic, value, ts})
                │   Redis PUBLISH "ws:topic:realtime.stream"
                ▼
        WsBridge._dispatch → ConnectionManager.send_local
                │   per-conn asyncio.Queue → writer task → WebSocket frame
                ▼
Streamlit RealtimeWsClient（daemon thread, asyncio.new_event_loop）
        ├── POST {http_base}/ws/ticket  Bearer JWT → ticket
        ├── WS  {ws_base}/ws?ticket={ticket}
        ├── send {"type":"subscribe","topic":"realtime.stream"}
        └── recv {"type":"data","topic":"realtime.stream","value":42.3,"ts":"..."}
                │   _on_reading(Reading(ts=..., value=42.3))
                │   threading.Lock → self._buffer = trim(old + [r], MAX_POINTS)
                ▼
st.fragment(run_every=1.0)
  buffer = ws.buffer   （thread-safe 快照）
  → 渲染圖表（第 1 段，不變）
```

---

### `lib/realtime_ws.py` 模組契約（新增）

**設計約束**：
- Streamlit 的 session 是單執行緒；WS 連線不能在主執行緒以 `asyncio.run()` 阻塞。
- 方案：一個 `daemon=True` 的背景執行緒，執行緒內自建獨立 `asyncio.new_event_loop()`。
- 緩衝以 `threading.Lock` 保護（**不**直接寫 `st.session_state`，避免跨執行緒 Streamlit 內部狀態衝突）；fragment 每秒以 `ws.buffer` 屬性讀出快照。

#### 公開 API

```python
class RealtimeWsClient:
    def __init__(
        self,
        *,
        http_base: str,          # fastapi_base_url（http/https）
        ws_base: str,            # fastapi_ws_url（ws/wss）
        get_token: Callable[[], str],   # lambda: st.session_state.get("access_token","")
    ) -> None: ...

    def start(self) -> None:
        """啟動 daemon 執行緒；連線與訂閱在執行緒內非同步完成。"""

    def stop(self) -> None:
        """設定 stop 事件；執行緒最多 30 s（backoff 上限）內自行退出。"""

    @property
    def buffer(self) -> list[Reading]:
        """thread-safe 快照（copy）；fragment 每幀讀此值、不持有 lock。"""

    @property
    def last_error(self) -> str | None:
        """最近一次連線 / 訂閱 / 讀取失敗的訊息；`None` 表示正常。"""
```

#### 內部設計

```python
# 執行緒進入點（不對外暴露）
def _run_with_reconnect(
    http_base, ws_base, get_token,
    on_reading: Callable[[Reading], None],
    stop: threading.Event,
    on_error: Callable[[str], None],
) -> None:
    loop = asyncio.new_event_loop()
    wait = 1.0
    while not stop.is_set():
        try:
            loop.run_until_complete(
                _connect_and_subscribe(http_base, ws_base, get_token, on_reading, stop)
            )
            wait = 1.0   # 正常完成（stop 設定），直接退出
        except Exception as exc:
            on_error(str(exc))
            stop.wait(timeout=wait)             # 指數退避（1 → 2 → 4 → … ≤ 30 s）
            wait = min(wait * 2, 30.0)
```

```python
async def _connect_and_subscribe(http_base, ws_base, get_token, on_reading, stop):
    # 1. 取 ticket
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{http_base}/ws/ticket",
            headers={"Authorization": f"Bearer {get_token()}"},
        )
        resp.raise_for_status()
        ticket = resp.json()["ticket"]

    # 2. WS 連線 + 訂閱 + 接收
    async with websockets.connect(f"{ws_base}/ws?ticket={ticket}") as ws:
        await ws.send(json.dumps({"type": "subscribe", "topic": "realtime.stream"}))
        async for raw in ws:
            if stop.is_set():
                break
            msg = json.loads(raw)
            if msg.get("type") == "data" and msg.get("topic") == "realtime.stream":
                on_reading(Reading(
                    ts=datetime.fromisoformat(msg["ts"]).astimezone(),   # UTC → 本地
                    value=float(msg["value"]),
                ))
```

**Backoff 細節**：初始 1 s，每次失敗翻倍，上限 30 s；`stop.wait(timeout=wait)` 使 stop 事件立即中斷等待（不讓 session 結束後仍在掛起）。

**Token 注入**：`get_token: Callable[[], str]` 設計為 lambda 捕捉 `session_state`，讓 `RealtimeWsClient` 與 Streamlit 解耦且可在 unit test 注入 stub。

---

### `lib/config.py` 補充

在 `BaseAppSettings` 加 `fastapi_ws_url` property（不是設定項，由 `fastapi_base_url` 衍生）：

```python
@property
def fastapi_ws_url(self) -> str:
    """將 http(s) URL 轉為對應的 ws(s) URL。"""
    return (
        self.fastapi_base_url
        .replace("https://", "wss://")
        .replace("http://", "ws://")
    )
```

> 替換順序釘死：先處理 `https`（含 `http` 前綴），再處理 `http`；避免 `https://` 被先替換為 `wss//` 後找不到 `http://` 的問題。

---

### 頁面改動（`pages/realtime_monitor.py`）

#### fragment 外：初始化 WsClient

```python
# DATA_SOURCE=api 時，於頁面進入時初始化並啟動 WS client（一次性）
if settings.data_source == "api" and "rt_ws_client" not in st.session_state:
    ws = RealtimeWsClient(
        http_base=settings.fastapi_base_url,
        ws_base=settings.fastapi_ws_url,
        get_token=lambda: st.session_state.get("access_token", ""),
    )
    ws.start()
    st.session_state["rt_ws_client"] = ws
```

#### `live_panel()` 第 1 段：`buffer` 來源切換

```python
@st.fragment(run_every=1.0)
def live_panel():
    # ── 1) 渲染（不變）──
    if settings.data_source == "api":
        ws: RealtimeWsClient = st.session_state["rt_ws_client"]
        if ws.last_error:
            render_error(ws.last_error)
            return                          # 停止刷新（early return）
        buffer = ws.buffer
    else:
        buffer = st.session_state["rt_buffer"]

    threshold = st.session_state.get("rt_threshold", int(DEFAULT_THRESHOLD))
    if not buffer:
        empty_state("資料串流啟動中…")
    else:
        st.caption(f"最後更新 {buffer[-1].ts.strftime('%H:%M:%S')}")
        metric_cards(summary_metrics(buffer, threshold))
        if is_over(buffer[-1].value, threshold):
            st.toast(alert_message(buffer[-1].value, threshold), icon="⚠️")
        st.altair_chart(build_chart(buffer, "line"), use_container_width=True)
        st.altair_chart(build_chart(buffer[-RECENT_POINTS:], "bar"), use_container_width=True)

    # ── 2) 生成（mock 專屬，DATA_SOURCE=mock 時才執行）──
    if settings.data_source != "api":
        tick = st.session_state["rt_tick"]
        reading = Reading(ts=datetime.now().astimezone(), value=sample_value(tick))
        st.session_state["rt_buffer"] = trim(buffer + [reading], MAX_POINTS)
        st.session_state["rt_tick"] = tick + 1
```

> **執行序釘死**：`buffer = ws.buffer` 先讀快照，再依快照渲染，無需改變 render-then-sample 模型——WS 模型天然是「非同步到達 → 渲染當前快照」，語意對齊。

#### Session 結束清理（可選）

```python
# 可在 app.py on_close / session_state 清理鉤子呼叫
if "rt_ws_client" in st.session_state:
    st.session_state["rt_ws_client"].stop()
```

---

### session_state 契約（新增 key）

現有 key（`rt_buffer`、`rt_tick`、`rt_threshold`、`rt_last_error`）延續不變；新增：

| Key | 型別 | 說明 | 生命週期 |
|---|---|---|---|
| `rt_ws_client` | `RealtimeWsClient` | WS client 實例（`DATA_SOURCE=api` 時初始化）；daemon 執行緒持有 `_buffer` 與 `_lock`，fragment 透過 `.buffer` 屬性讀快照。 | 頁面進入時建立；session 結束 / `stop()` 後執行緒退出 |

> `rt_last_error` 由 `ws.last_error` property 代理（WS client 內部持有），`session_state` 層不再單獨寫入；mock 階段 `rt_last_error` 仍作為預留 key 記錄（見 §session_state 契約）。

---

### 狀態與錯誤處理（接後端）

| 情境 | 呈現 |
|---|---|
| 緩衝為空（WS 尚未收到第一筆） | `empty_state("資料串流啟動中…")` 取代圖表（同 mock 首幀，語意一致） |
| 目前值 > 閾值 | toast overlay + 「目前值」卡 inverse delta（同 mock） |
| WS ticket 取得失敗（401/503） | `ws.last_error` 設值 → `render_error(ws.last_error)` + `return`（停止 fragment 繼續刷新） |
| WS 連線中斷 | RealtimeWsClient 自動指數退避重連（1→2→4…≤30 s）；重連中 `ws.buffer` 保留最後已知值，直到 `last_error` 設值才呈現 error |
| WS 訊息格式異常（parse error） | 該筆跳過（`_on_reading` 捕捉 `ValueError`）；`last_error` 不設值，下一筆正常消費 |

---

### lib/ 依賴（接後端新增）

| 模組 | 用途 |
|---|---|
| `lib/realtime_ws.py` | WS client（`RealtimeWsClient`）|
| `websockets` | async WS 連線（`websockets.connect`）；需加入 `pyproject.toml` |
| `httpx` | 取 WS ticket（`POST /ws/ticket`）；已為既有相依 |

---

### 可測試性 / TDD（接後端）

> 延伸既有 §可測試性 / TDD；編號接續（18 起）。

#### 純函式 / 單元（`tests/unit/test_realtime_ws.py`）

18. **`_http_to_ws` 轉換**（等效驗算 `config.fastapi_ws_url` 邏輯）：`http://a` → `ws://a`；`https://b` → `wss://b`；`https://` 不會雙重替換為 `wsss://`。
19. **`_on_reading` 更新緩衝**：建立 client（不呼叫 `start()`），直接呼叫 `_on_reading(r)`，`ws.buffer == [r]`；連續呼叫超過 `MAX_POINTS` → `trim` 生效（`len(ws.buffer) == MAX_POINTS`）。
20. **`_on_error` 設 `last_error`**：呼叫 `_on_error("bad")` → `ws.last_error == "bad"`；接著 `_on_reading(r)` → `ws.last_error is None`（收到資料時清除錯誤）。
21. **`stop()` 中斷 backoff**：mock `_connect_and_subscribe` 拋例外；啟動執行緒後立即 `ws.stop()`，確認執行緒於合理時間（< 1 s）退出（不因 backoff wait 掛住）。
22. **UTC → 本地時區轉換**：`_on_reading` 收到 UTC isoformat ts → `Reading.ts.tzinfo` 為本地時區（`utcoffset()` 等於本機偏移）。

#### 頁面行為（`tests/app/test_realtime_monitor.py`，AppTest，接後端）

> 以 mock `RealtimeWsClient` 注入 `session_state`（`rt_ws_client`）；不啟動真實執行緒，不連真實後端。模式切換以 `monkeypatch` 覆寫 `settings.use_mock = False`（或直接 patch `lib.config.get_settings`）。

23. **WS buffer 渲染**：注入帶 `buffer=[Reading(now, 42.0)]`、`last_error=None` 的 mock ws 至 `rt_ws_client` → fragment 含 `st.metric`（指標卡），不顯示 `st.info`。
24. **WS 連線失敗呈現**：注入 `last_error="connection refused"` → fragment 含 `render_error` 輸出（`st.error`）、**不含** `st.metric`（提前 return）。
25. **WS 緩衝為空呈現**：注入 `buffer=[]`、`last_error=None` → 顯示 `empty_state("資料串流啟動中…")`（同 mock 測試 17，語意對齊）。

> 依 `CLAUDE.md`：先寫失敗測試（RED）→ 最小實作（GREEN）→ 全綠後重構。
> 順序：`lib/realtime_ws.py` unit（18–22）→ config property 單元 → 頁面 AppTest（23–25）。
</content>
</invoke>
