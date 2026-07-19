# 規格:錯誤處理(單一事實來源)

本規格是 StreamSight Streamlit 前端「錯誤處理」的**導覽中樞**與**呈現契約的權威來源**。目的:把原本散在 `api-client` / `data-source` / `auth` / `request-id` 與各頁面的錯誤約定收斂到一處,消除「同一種錯誤在不同頁面被不同方式描述」的分歧。

- 前提:[ADR 0002](../decisions/0002-streamlit-as-api-client.md)(純 API Client,不連 DB)。
- **權威分工(硬性,避免雙重來源)**:
  - **狀態 → 例外映射**:權威在 [API Client §3.2](api-client.md),本規格只彙整、不重定義。
  - **例外語意與定義位置**:權威在各模組(`models.py` / `auth.py`),本規格提供**目錄**與交叉引用。
  - **例外 → 呈現(層級 / 文案 / request_id)**:**本規格為唯一權威**(§3、§4);各頁面一律引用本表,不自訂。
  - **視覺格式(顏色 token / 訊息樣式)**:權威在 [設計系統](design-system.md#狀態色彩規範);本規格引用。

---

## 1. 分層與職責(錯誤在哪裡發生、由誰處理)

錯誤處理不是單一動作,而是發生在**三個呼叫點、依賴三種不同東西**的三件事——刻意分層,不合併:

| 層 | 職責 | 產物 | 位置 |
|---|---|---|---|
| **傳輸層** | HTTP 狀態 → 例外映射、逾時 / 連線 → `ApiError`、附 `request_id`、結構化 log | 例外(帶 `request_id`) | `lib/api_client.py`(見 [api-client §3、§4](api-client.md)) |
| **控制流** | 401 reactive refresh、GET 網路重試(冪等) | 重試 / 換 token 後重呼 | `lib/api_client.py` + `lib/auth.py`(見 [api-client §5](api-client.md)) |
| **呈現層** | 攔例外 → 統一翻成(層級 / 文案 / request_id)→ 呼對應 `st.*` | 使用者可見訊息 | `lib/errors.py`(本規格 §5)+ 各頁面 |

> **為何不做單一 error handler**:上表三件事各自綁在不同呼叫點與相依(HTTP `Response` + 冪等性 / auth token + 控制流 / Streamlit runtime),合併只會把已分層的架構重新黏死、更難測。本規格統一的是**知識**(下方各表),而非**執行**。

---

## 2. 錯誤分類目錄(taxonomy — 指向定義,不重定義)

| 例外 / 狀況 | 語意 | 定義位置 | 對應狀態 |
|---|---|---|---|
| `ValidationError` | 使用者輸入不合法(必填空、`category` 不在清單、`value` 非數、非法 `sort` 欄位) | `lib/models.py`(見 [data-source §例外](data-source.md#例外)) | 400 / 422 |
| `PermissionDenied` | 無寫入權限（`grade == 0`，即 viewer）的 create/update/delete | `lib/models.py`(見 [data-source §例外](data-source.md#例外)) | 403 |
| `RecordNotFound` | 目標不存在或已軟刪除 | `lib/models.py`(見 [data-source §例外](data-source.md#例外)) | 404 |
| `NotAuthenticated` | reactive refresh 後仍 401,session 失效 | `lib/models.py`(見 [auth §5](auth.md)、[api-client §3.2](api-client.md)) | 401(重試後) |
| `ApiError` | 逾時 / 連線錯誤 / 408 / 429 / 5xx / 非預期狀態 / 後端契約破壞 | `lib/api_client.py`(見 [api-client §3.1](api-client.md)) | 5xx / None / 其他 |

- 域例外(`ValidationError` / `PermissionDenied` / `RecordNotFound`)**與 `MockDataSource` 同契約**——刻意與 `Record`/`Actor`/`can_edit` 同放 `lib/models.py`,mock/api 兩路徑錯誤處理一致。
- `ApiError` 一律帶 `.request_id`;`.status` 於逾時 / 連線錯誤為 `None`(見 [api-client §3.1](api-client.md))。
- **狀態 → 例外映射的權威表在 [api-client §3.2](api-client.md)**,此處不複製,以免雙重來源。

---

## 3. 呈現契約(本規格唯一權威)

攔到例外後,一律經 `lib/errors.py` 翻成下列 `(層級, 文案, 是否附 request_id, 呈現位置)`。**各頁面不得自訂**,只能引用本表。

| 例外 / 狀況 | 層級 | 使用者文案(範例) | 附 `request_id` | 呈現位置 / 行為 |
|---|---|---|---|---|
| `ValidationError`(400/422) | `error` | 「欄位不合法:{原因}」 | ❌ | 表單旁 `st.error`;不刷新,保留使用者輸入 |
| `PermissionDenied`(403) | `error` | 「你沒有權限執行此操作」 | ❌ | 操作處 `st.error`;**按鈕應預先停用**以避免觸發 |
| `RecordNotFound`(404) | `warning` | 「資料不存在或已被移除」 | ❌ | 列表區 `st.warning` + 刷新列表 |
| `NotAuthenticated`(401×2) | — | (不顯訊息) | — | **清 session + 清快取 + 導向主前端登入**(見 [auth §5](auth.md)) |
| `ApiError`(408/429/5xx) | `error` | 「操作失敗,請稍後再試。錯誤代碼:{rid}」 | ✅ | 保留頁面框架、**可重試**;寫 `last_request_id` |
| `ApiError`(逾時 / 連線,`status=None`) | `error`※ | 「暫時無法連線,請稍後重試。錯誤代碼:{rid}」 | ✅ | 保留頁面框架、可重試;寫 `last_request_id` |
| `ApiError`(後端契約破壞:缺欄位 / 型別不符) | `error` | 「系統資料異常,請回報。錯誤代碼:{rid}」 | ✅ | 保留頁面框架;寫 `last_request_id`(見 [api-client §7](api-client.md)) |
| 空資料(**非錯誤**) | `info` | 「目前範圍內沒有資料」 | ❌ | `st.info` **取代主內容區**;分析頁另**停用匯出** |
| WebSocket 斷線(重連中) | `warning` | 「連線中斷,重連中…」 | ❌ | 狀態橫幅;自動重連,不阻斷既有畫面 |
| WebSocket 重連失敗(超過上限) | `error` | 「即時連線失敗,請重新整理頁面。」 | ❌ | 狀態橫幅 `st.error`;**停止自動刷新**,提供手動重連 |

> ※ **auth gate 導向頁(頁 1)例外**:introspection 逾時 / BFF 不可用時改用 `info`(「暫時無法連線,請稍後重試」)+ 手動「前往登入」後備——因該頁是登入前的引導頁,不宜用 error 色突顯。此為**唯一**允許偏離本表層級的情境,見 [01-login §狀態與錯誤處理](pages/01-login.md#狀態與錯誤處理)。

### 3.1 `request_id` 呈現政策(決策)

**只有傳輸 / 系統層錯誤(`ApiError`,含逾時 / 連線 / 契約破壞)才在 UI 附 `request_id`**,並寫入 `session_state["last_request_id"]`(見 [request-id §4.3、§5](request-id.md))。

- **理由**:`request_id` 是給客服對照三端 log 用的;使用者可自行修正的錯誤(Validation / Permission / NotFound)附上神秘代碼只會增加雜訊。
- 與 [request-id §5](request-id.md) 一致:`last_request_id` 只暫存「最近一次**失敗**(ApiError)」的 ID,成功不留。
- 呈現格式見 [設計系統 §訊息呈現規範](design-system.md#訊息呈現規範)(等寬、附於訊息末)。

### 3.2 層級選用規則(`st.error` / `st.warning` / `st.info`)

| 層級 | 適用 | 色 token |
|---|---|---|
| `error` | 操作失敗、系統 / 傳輸故障、使用者輸入需修正 | danger |
| `warning` | 可恢復 / 暫時性 / 降級中(WS 重連、找不到目標) | warning |
| `info` | 空狀態、登入前引導 | (中性 / secondary) |

---

## 4. 跨頁一致性總表(各頁情境 → 引用本規格)

各頁面的「狀態與錯誤處理」段一律**引用**下列對映,不再各寫各的:

| 情境 | 頁面 | 依 §3 呈現 |
|---|---|---|
| 查詢 / 載入失敗 | 資料管理、分析、admin | `ApiError` → `error` + 保留頁框 + 可重試(+ rid) |
| 無資料 | 資料管理、即時監控、分析 | `info` 取代主內容;分析另停用匯出 |
| 無權限操作 | 資料管理、admin | 按鈕預先停用;觸發則 `PermissionDenied` → `error` |
| 找不到資料 | 資料管理 | `RecordNotFound` → `warning` + 刷新 |
| 輸入不合法 | 資料管理(表單) | `ValidationError` → 表單旁 `error` |
| session 失效 | 全站 | `NotAuthenticated` → 導向登入 |
| introspection 逾時 | 登入導向頁 | `info`(§3 ※ 例外)+ 手動後備 |
| WS 斷線 / 重連失敗 | 即時監控 | 斷線 `warning`;超上限 `error` + 停刷新 |
| 匯入部分失敗 | 資料管理 | 逐列標示問題列(`ImportResult.errors`),不中斷其餘 |

---

## 5. 呈現 helper(`lib/errors.py`)

薄的**純邏輯 + 薄 UI 綁定**,把 §3 的表落成單一實作;符合 CLAUDE.md「邏輯與 UI 分離、純函式好測」。

```python
# lib/errors.py(概念,非最終碼)
from dataclasses import dataclass
from typing import Literal, Optional

Level = Literal["error", "warning", "info"]

@dataclass(frozen=True)
class ErrorView:
    level: Level
    text: str                       # 已本地化的使用者文案
    request_id: Optional[str] = None  # 僅 ApiError 類帶值(§3.1)
    code: Optional[str] = None        # 後端錯誤 code(可選,待封包格式定案)

def to_user_message(exc: Exception) -> ErrorView:
    """把任意被攔到的例外翻成 §3 的 (層級, 文案, request_id)。純函式,不碰 Streamlit。"""
    ...

def render_error(exc: Exception) -> None:
    """薄 UI 綁定:呼 to_user_message,依 level 呼 st.error/warning/info,
    ApiError 類自動附「錯誤代碼:{rid}」並寫 session_state['last_request_id']。"""
    ...
```

- `to_user_message` **純函式**:餵例外、斷言輸出 `ErrorView`,無需 Streamlit runtime,unit test 直接覆蓋 §3 每一列。
- `render_error` 是唯一寫 `st.*` 與 `last_request_id` 的地方——把「記得顯示 request_id」從 6 頁收斂成 1 處。
- **不做**:狀態→例外映射(在 `api_client._handle`)、重試 / refresh(在 `api_client` §5 + `auth`)、401 導向(在 `app.py`)。本模組只負責「例外 → 呈現」。

---

## 6. Fallback 契約(把外部待確認釘成確定路徑,不阻塞實作)

兩個尚未與外部對齊的項目,**規格層先定 fallback,使實作路徑確定**;外部定案後再補強化分支。

| 待確認 | 現階段確定行為(fallback) | 定案後強化 |
|---|---|---|
| **後端錯誤封包格式**(假設 `{"error":{code,message}}`,見 [api-client §3.3、§8](api-client.md)) | 解析不到標準封包 → `code=None`,文案退回「HTTP 狀態 + §3 通用文案」;`ApiError.message` 存原文供 log(**不顯示於 UI**) | 封包定案 → 由 `code` 對映更精準文案,補進 `to_user_message` 的 `code` 分支 |
| **`st.context.cookies` 能否讀 httpOnly**(見 [auth-flow §8 spike-1](auth-flow.md#8-tdd-測試計畫)) | 標為**實作前必驗**;未過**不得往下**——因整個 cookie 轉發認證機制依賴它 | 若讀不到 → 改 OAuth redirect 換 code,認證與錯誤導向流程需重寫(另立規格) |

- 後端原文 / stack trace **一律不揭露於 UI**,只進結構化 log(遮蔽規則見 [request-id §4.2](request-id.md))。

---

## 7. 可測試性 / TDD

依 CLAUDE.md 逐一先寫失敗測試。放 `tests/unit/test_errors.py`:

### 純模組(**現在即可實作**——不依賴 api_client / Streamlit)

1. `to_user_message(PermissionDenied())` → `level="error"`、`request_id is None`。
2. `to_user_message(RecordNotFound())` → `level="warning"`、`request_id is None`。
3. `to_user_message(ValidationError("category 不合法"))` → `level="error"`、文案含原因、`request_id is None`。
4. `to_user_message(ApiError("逾時", status=None, request_id="st-abc"))` → `level="error"`、`request_id=="st-abc"`、文案含「錯誤代碼」佔位。
5. `ApiError(status=500, request_id=rid)` → `level="error"`、帶 `rid`。
6. **request_id 政策** — 域例外(1–3)一律 `request_id is None`;`ApiError`(4–5)一律帶值。
7. **後端封包 fallback** — `code=None` 時退回通用文案,不炸(§6)。

### 呈現綁定(`tests/app/`,AppTest,可選)——gated on 頁面接線

8. `render_error(ApiError(...))` → 畫面出現 `st.error` 且含「錯誤代碼:st-…」;`session_state["last_request_id"]` 有值。
9. `render_error(PermissionDenied())` → `st.error` 且**不含**「錯誤代碼」;`last_request_id` **不被寫入**。

> 純模組(1–7)不需 `api_client` 存在即可先行 RED → Green;綁定(8–9)待頁面接線後補。

---

## 8. 相依 / 待確認

- [x] **呈現契約**:層級 / 文案 / request_id 政策已定案(§3),為各頁唯一權威。
- [x] **權威分工**:映射權威留 api-client §3.2、視覺格式留 design-system、呈現契約歸本規格——無雙重來源。
- [x] **fallback 契約**:後端封包未定 / httpOnly 未驗時的確定行為已定(§6),不阻塞 `lib/errors.py` 實作。
- [ ] **後端錯誤封包格式**:需與後端 / BFF 對齊(承 [api-client §8](api-client.md));定案後補 `code→文案`。
- [ ] **`st.context.cookies` httpOnly**:實作前必跑 [auth-flow §8 spike-1](auth-flow.md#8-tdd-測試計畫)。
- [ ] **WS 重連上限值**:自動重連幾次後判定「重連失敗」轉 `error`?待即時監控實作時定(見 [04-realtime-monitor](pages/04-realtime-monitor.md#狀態與錯誤處理))。

---

## 9. 檔案與掛載

```
lib/
├── errors.py        # 本規格:ErrorView / to_user_message / render_error(§5)
├── api_client.py    # 傳輸層:ApiError + 狀態→例外映射(_handle)+ request_id(§1)
├── models.py        # 域例外 + Record/Actor/can_edit(§2 目錄指向此)
├── auth.py          # NotAuthenticated 拋出時機、清狀態導向(§3)
└── request_id.py    # request_id 產生 / last_request_id 暫存(§3.1)
tests/unit/test_errors.py   # 純模組(測 1–7),現可實作
```

> 於 [應用骨架 §6 lib 分層總表](app-skeleton.md#6-lib-分層總表單一入口地圖) 登錄 `lib/errors.py`;必要性為**接 API 階段**(全 mock 下,呈現契約仍適用於域例外)。

---

## 10. 相關文件

- [API Client](api-client.md)(錯誤模型 §3、單次呼叫 §4、重試 §5)
- [資料來源](data-source.md)(域例外定義)
- [認證流程](auth-flow.md)(401 導向、httpOnly spike)
- [Request ID 模組](request-id.md)(request_id 呈現與暫存)
- [設計系統](design-system.md#訊息呈現規範)(顏色 token 與訊息樣式)
- [前端頁面結構](frontend-pages.md)
