# 規格：閒置逾時自動登出（Idle Timeout）

使用者連續閒置（無滑鼠 / 鍵盤活動）逾 **15 分鐘** 即自動登出。採**純前端 JS 偵測**，定義偵測機制、登出範圍、逾時原因提示，以及符合本專案架構的模組分層與 TDD 計畫。

- 對應模組：模組 1 認證（延伸）
- 關聯：[認證流程 §4.5 登出](auth-flow.md#45-登出)、[登出接線規格](logout.md)、[Auth 模組](auth.md)、[主題切換 §5](theme-toggle.md)（JS 注入模式參照）、[設定模組](config.md)
- 狀態：**草稿（待實作）** — 2026-07-19 定案設計方向，尚未進 TDD 循環。

---

## 0. 決策紀錄（2026-07-19）

| # | 決策項 | 選定 | 理由 / 影響 |
|---|---|---|---|
| D1 | **登出範圍** | **全 SSO 登出** | 逾時 → 走既有 `auth.logout()` → BFF `POST /api/auth/logout`，使 Redis session 失效並清共享 cookie。符合「閒置＝結束 session」的資安慣例；副作用：同時登出 Next.js 主前端（可接受）。 |
| D2 | **閒置偵測機制** | **純前端 JS，偵測滑鼠 / 鍵盤活動** | 前端 JS 計時器監聽滑鼠與鍵盤事件，連續無活動達門檻即主動導向登出。**不做伺服器端兜底層**（簡化）。 |
| D3 | **逾時權威層** | **Streamlit 自行實作（本 repo）** | 不依賴 BFF 新增 idle 政策；範圍限本 repo、可立即開發。 |
| D4 | **逾時提示** | **不做逾時前倒數警告；於登出時提示原因**（「因閒置逾 15 分鐘，已登出」） | 不新增 warning 計時器；改在登出後把「原因」帶到登入頁 / 提示上呈現。 |

> **D2 的取捨（誠實揭露）**：純前端偵測即時、實作簡單，但 JS 若被停用 / 繞過即不生效——此時**不會**有 Streamlit 端的閒置登出。安全兜底仍在既有機制：BFF session 的自身壽命與 introspection 401 流程（見 §6.1）。若日後需伺服器端權威，另立規格補上；本規格範圍內**不含**。

---

## 1. 目的與範圍

### 1.1 目的

在既有「登入委派 Next.js、Streamlit 為薄 API Client」架構上，以**純前端 JS** 新增閒置逾時自動登出：使用者在 Streamlit 儀表板連續無**滑鼠 / 鍵盤**操作達 `IDLE_TIMEOUT_SECONDS`（預設 900 秒＝15 分）後，自動觸發登出流程並導向登入頁，且明確告知登出原因為閒置逾時。

### 1.2 範圍內

- **前端 JS 閒置偵測**（滑鼠 / 鍵盤活動、計時器、跨分頁同步）（§4）。
- 逾時後的**登出流程**（重用 `?logout=1` 訊號，附帶 `reason=idle`）（§5）。
- 逾時**原因提示**（bff 導向登入頁 / mock 本地重進兩模式）（§6）。
- 模組分層、設定項、TDD 測試計畫（§7、§8）。

### 1.3 範圍外

- **伺服器端閒置兜底**（D2 決定不做）。
- `auth.logout()` 本身的 BFF 呼叫與 CSRF 細節：已定義於 [auth-flow §4.5](auth-flow.md#45-登出) 與 [logout.md](logout.md)。
- BFF / Redis 端 session 壽命與其自身 idle 政策：屬主前端 spec。
- token refresh 門檻與 introspection 快取：已定義於 [auth-flow §4.3/§4.6](auth-flow.md#43-呼叫-fastapi-業務-api--token-過期處理)。
- 逾時前倒數警告 UI：依 D4 不納入。

---

## 2. 為何用前端 JS 偵測

Streamlit **每次互動才重跑整個 script**。使用者若完全不動，**伺服器端不會觸發任何 rerun**，純伺服器端無法主動把閒置分頁踢出。**前端 JS 計時器**能即時監聽滑鼠 / 鍵盤活動並在到點時主動導向登出，正好補上這個缺口，且實作最單純。

（本規格依 D2 只採此單層；不做伺服器端兜底。）

---

## 3. 職責邊界

| | 偵測閒置（滑鼠 / 鍵盤） | 判定逾時 | 執行登出（使 session 失效） |
|---|---|---|---|
| **Client JS** | ✅ | ✅（計時到點 → 導向 `?logout=1&reason=idle`） | ❌（僅發訊號） |
| **Streamlit server** | ❌ | ❌ | ✅（收到 `?logout=1` → 呼叫 `auth.logout()`） |
| **主前端 BFF** | ❌ | ❌ | ✅（真正使 Redis session 失效） |

> JS 只負責「偵測 + 發訊號」，真正登出仍由 Streamlit server 執行既有 `auth.logout()`（訊號不等於已登出，同 [logout.md §2.2](logout.md#2-技術方案a-hreflogout1--apppy-查詢參數偵測)）。

---

## 4. 前端 JS 閒置偵測

### 4.1 注入方式

沿用 [theme-toggle §5](theme-toggle.md) 既有模式，以 `st.components.v1.html(f"<script>{JS}</script>", height=0)` 於 `app.py` 每次 rerun 注入（冪等）。元件跑在 iframe 內，一律透過 `window.parent.document` 操作主文件（與 `inject_theme_js` 相同）。

### 4.2 行為

1. 監聽主文件的**滑鼠與鍵盤**活動事件：
   - 滑鼠：`mousemove`、`mousedown`、`wheel`
   - 鍵盤：`keydown`
   - （`passive` 監聽，不阻塞捲動）
2. 每次活動**重置**計時器；活動處理以 `IDLE_ACTIVITY_THROTTLE_SECONDS`（預設 30s）節流，避免 `mousemove` 高頻洗版。
3. 計時器到點（`IDLE_TIMEOUT_SECONDS`）→ 將**父視窗**導向 `?logout=1&reason=idle`（登出訊號，實際登出由 server 執行，見 §5）。
4. **跨分頁同步**：活動時間寫入 `localStorage['ss_last_activity']`；監聽 `storage` 事件，任一分頁有活動即重置本分頁計時器（避免「A 分頁在用、B 分頁把 session 踢掉」）。
5. **冪等**：每次 rerun 重注入前，先呼叫上一輪掛在 `window.parent.__ssIdleCleanup` 的清理函式（移除舊監聽與計時器），避免堆疊。

### 4.3 純函式化（可測試）

JS 內容由 `lib/idle.py::build_idle_js(timeout_seconds, throttle_seconds)` 這支**純函式**產生（不依賴 Streamlit，對齊 `topbar._build_topbar_html` 模式）；`app.py` 只負責注入。

**JS 骨架（示意，非最終碼）**：

```js
(function () {
  var W = window.parent, D = W.document;
  var TIMEOUT_MS = {timeout_ms}, THROTTLE_MS = {throttle_ms};
  var KEY = 'ss_last_activity';
  if (W.__ssIdleCleanup) { W.__ssIdleCleanup(); }        // 冪等：清上一輪

  var timer = null, last = 0;
  var events = ['mousemove', 'mousedown', 'wheel', 'keydown'];  // 僅滑鼠 / 鍵盤

  function fireLogout() { W.location.href = '?logout=1&reason=idle'; }
  function schedule() { if (timer) W.clearTimeout(timer); timer = W.setTimeout(fireLogout, TIMEOUT_MS); }
  function onActivity() {
    var now = Date.now();
    if (now - last < THROTTLE_MS) return;                // 節流
    last = now;
    try { W.localStorage.setItem(KEY, String(now)); } catch (e) {}
    schedule();
  }
  function onStorage(e) { if (e.key === KEY) schedule(); }  // 跨分頁：他頁有活動 → 重置

  events.forEach(function (ev) { D.addEventListener(ev, onActivity, { passive: true }); });
  W.addEventListener('storage', onStorage);
  schedule();

  W.__ssIdleCleanup = function () {
    if (timer) W.clearTimeout(timer);
    events.forEach(function (ev) { D.removeEventListener(ev, onActivity, { passive: true }); });
    W.removeEventListener('storage', onStorage);
    W.__ssIdleCleanup = null;
  };
})();
```

---

## 5. 逾時登出流程（重用既有 `?logout=1` 接線）

**核心原則**：不新增第二套登出路徑。閒置逾時**收斂到既有 `?logout=1` 訊號**（見 [logout.md §2](logout.md#2-技術方案a-hreflogout1--apppy-查詢參數偵測)），僅**附帶原因** `reason=idle`。實際登出由 Python 端執行。

### 5.1 流程

1. JS 計時到點 → 父視窗導向 `?logout=1&reason=idle` → Streamlit rerun（帶 query param）。
2. `app.py` 在 `resolve_actor()` 之後偵測 `st.query_params.get("logout") == "1"`。
3. 解析 `reason`（白名單，§5.2）→ 呼叫 `auth.logout()`（既有行為，不改）。
4. 依模式呈現原因並導向 / 重進（§6）。

### 5.2 reason 白名單（安全）

`reason` 來自 query param（使用者可竄改），**僅供顯示、不參與任何安全判斷**。解析以白名單收斂：`reason in {"idle"}` 才視為有效閒置原因，否則忽略（走一般登出）。避免反射式內容注入。

### 5.3 與 `auth.logout()` 的關係

不改 `auth.logout()`。閒置登出照 [logout.md §3](logout.md#3-行為規格) 既有行為：

- **BFF 模式**：`auth.logout()` → `POST BFF logout`（帶 cookie＋CSRF＋Origin，try/finally 兜底清本地）→ 導向登入頁（附原因，見 §6.1）。
- **Mock 模式**：`auth.logout()` → `state.clear_auth()` → 清 param → rerun（附原因，見 §6.2）。

---

## 6. 逾時原因提示（D4）

不做逾時前倒數警告；於**登出當下 / 登出後**明確告知「因閒置逾 15 分鐘，已登出」。因 `?logout=1` 會清 param、bff 模式會整頁跳轉，需把原因**跨越 rerun / 跳轉**帶到呈現處。

### 6.1 BFF 模式

登入頁在 Next.js（跨 repo）。為求本 repo 自足，採**短暫過場頁**：

1. 偵測到閒置登出後，`auth.logout()` 清狀態。
2. Streamlit 渲染過場訊息「**因閒置逾 15 分鐘，已將您登出，正在導向登入頁…**」，並以**延時 meta refresh**（`content="3; url={bff_login_url}"`）於 3 秒後跳轉，讓訊息可見。
3. `st.stop()`。

> **選配（跨 repo 增強）**：亦可即時跳轉並於登入 URL 附 `?reason=session_timeout`，由 Next.js 登入頁渲染提示。需主前端配合（列為未決 §9），**非本規格必要路徑**；預設採過場頁。

### 6.2 Mock 模式

Mock 無登入頁；`auth.logout()` → 清 param → rerun 後以預設角色重進。原因需跨 rerun 保留：

1. 登出前寫 `st.session_state["_logout_reason"] = "idle"`（`clear_auth` 之後、`rerun` 之前設；`_logout_reason` 不在 `clear_auth` 清除清單內）。
2. 下一輪 rerun，`app.py` 偵測並以 `st.toast("因閒置逾 15 分鐘，已登出", icon="⏱️")`（或 `st.info`）呈現後 **pop** 掉旗標（只顯示一次）。

---

## 7. 模組分層與變更清單

沿用「純邏輯放 `lib/`、頁面薄」原則。

| 檔案 | 變更 | 測試 |
|---|---|---|
| `lib/idle.py`（**新增**） | 純函式：`build_idle_js(timeout_seconds, throttle_seconds)`、`parse_logout_reason(raw) -> Optional[str]`（白名單）；**Streamlit 接縫** `inject_idle_js()`（讀 `get_settings()` → `components.html(...)` 注入，對齊 `theme.inject_theme_js`） | unit（純函式）；AppTest（注入） |
| `lib/state.py` | 新增 `_LOGOUT_REASON` 與 `set_logout_reason` / `pop_logout_reason`（**不**列入 `clear_auth` 清除清單） | unit |
| `lib/config.py` | 新增 `idle_timeout_seconds: int = 900`、`idle_activity_throttle_seconds: int = 30` | unit |
| `docs/specs/config.md` | 新增 §3.8「閒置逾時」設定表（`IDLE_TIMEOUT_SECONDS` / `IDLE_ACTIVITY_THROTTLE_SECONDS`）——config 設定項的單一事實來源需同步 | — |
| `app.py` | ① `inject_idle_js()`（於 `inject_theme_js()` 附近，冪等）；② 既有 `?logout=1` 分支解析 `reason` 並帶入 `_handle_post_logout`；③ 於 `resolve_actor()` 之後、登出偵測**之前**加入 `_logout_reason` 顯示區塊（見 §7.1）；④ 既有登出分支重構為 `_handle_post_logout(reason)`（見 §7.2） | AppTest |
| `styles/main.css` | （選配）過場頁訊息樣式；能用主題就不寫 | — |
| `tests/unit/test_idle.py`（**新增**） | §8.1 | — |
| `tests/unit/test_state.py`、`test_config.py` | §8.1 增補 | — |
| `tests/app/test_app_skeleton.py` | §8.2 增補 | — |

### 7.1 `app.py` 插入點（示意）

```python
actor = resolve_actor()             # ③（不變）

if actor is None:                   # ④（不變）
    ...  # 跳轉登入頁（見 §7.3 edge case：此分支早於登出偵測）

# ④″ 閒置登出原因提示（新增，須在 actor 解析後、登出偵測前；只顯示一次）
_reason = state.pop_logout_reason()          # 讀後即清
if _reason == "idle":
    st.toast("因閒置逾 15 分鐘，已登出", icon="⏱️")

# ④′ 登出偵測（既有 ?logout=1 分支，擴充解析 reason）
if st.query_params.get("logout") == "1":
    reason = idle.parse_logout_reason(st.query_params.get("reason"))  # 白名單
    logout()
    _handle_post_logout(reason)     # 見 §7.2；依 reason 決定過場頁 / 即時跳轉
    st.stop()

# ⑤ 開發切換器（不變）...
inject_idle_js()                    # 與 inject_theme_js 併列，冪等注入
```

> `_reason` 顯示區塊放在 `actor is None` 之後，確保 mock 登出後（已以預設角色重進、`actor` 非 None）能顯示 toast；bff 模式因整頁跳轉到 Next.js，過場頁已在 §6.1 顯示原因，`_logout_reason` 走 mock 路徑不衝突。

### 7.2 `_handle_post_logout(reason)`（既有登出分支的重構）

現行 `app.py`（`logout.md §4.2`）登出後：mock 清 param＋rerun；bff 即時 `meta refresh content="0"`。本規格把這段抽成 `_handle_post_logout(reason)`，**依 reason 分岔**，並確保**手動登出行為不變**：

| 模式 | reason | 行為 |
|---|---|---|
| mock | 任意 | `state.set_logout_reason(reason)`（若為 `"idle"`）→ `st.query_params.clear()` → `st.rerun()` |
| bff | `None`（手動登出） | 即時 `meta refresh content="0; url={bff_login_url}"` + `st.stop()`（**與現況一致，不得變慢**） |
| bff | `"idle"` | 過場頁訊息 + 延時 `meta refresh content="3; url={bff_login_url}"` + `st.stop()`（§6.1） |

> 重點：**手動登出（TopBar）不帶 `reason` → 一律即時跳轉**，不受本規格拖慢；只有閒置（`reason=idle`）才走過場頁。

### 7.3 已知 edge case

`actor is None`（BFF session 已失效）分支在 `app.py` **早於**登出偵測。若 JS 計時到點時 session 剛好已過期，導向 `?logout=1&reason=idle` 後會先命中 `actor is None` → 直接跳登入頁，**閒置提示遺失**（使用者仍正確落在登入頁，只是少了「因閒置」文案）。此為可接受降級，不另處理。

---

## 8. TDD 測試計畫

> 依 [CLAUDE.md](../../CLAUDE.md) 嚴格 TDD：每個行為**先寫失敗測試**再補最小實作。以下為行為清單（Red 目標）。

### 8.1 `tests/unit/`

**`test_idle.py`**

- `build_idle_js` 內容：含正確 `timeout_ms`（= `timeout_seconds * 1000`）、`throttle_ms`、`?logout=1&reason=idle` 導向、`__ssIdleCleanup` 冪等清理；監聽事件**含** `mousemove`/`mousedown`/`wheel`/`keydown`，**不含** `touchstart`（僅滑鼠 / 鍵盤）。
- `parse_logout_reason`：`"idle"` → `"idle"`；未知值 / `None` / 空字串 / 注入字串 → `None`（白名單）。

**`test_state.py`（增補）**

- `set/pop_logout_reason`：pop 後不再存在；`clear_auth()` **不**清 `_logout_reason`。

**`test_config.py`（增補）**

- `idle_timeout_seconds` 預設 900、`idle_activity_throttle_seconds` 預設 30；可由環境變數覆寫。

### 8.2 `tests/app/test_app_skeleton.py`（增補）

> 沿用 [logout.md §5.2](logout.md#52-testsapptest_app_skeletonpy新增-3-個已實作) 的 AppTest 限制與 **spy `auth.logout`** 手法（`st.query_params.clear()` 在單次 `at.run()` 內不可觀察；找 topbar/JS 需精確字串匹配避開 `<style>` 區塊）。

- **idle JS 已注入**：`at.run()` 後元件 / markdown 含 idle 計時器特徵字串（`__ssIdleCleanup` 或 `reason=idle`）。
- **mock 閒置登出＋原因提示**（spy logout）：`?logout=1&reason=idle` → `auth.logout()` 被呼叫；下一輪 rerun 出現「因閒置逾 15 分鐘」toast/info，且 `_logout_reason` 被 pop（再下一輪不再出現）。
- **bff 閒置導向**（`USE_MOCK=0`，patch `lib.auth` 內部函式如 logout.md §5.2）：`?logout=1&reason=idle` → `_do_logout_bff` 被呼叫 → markdown 含 meta refresh 導向登入頁與過場訊息。
- **reason 白名單**：`?logout=1&reason=<script>` → 走一般登出、不顯示閒置提示、不反射該字串。

### 8.3 手動驗證（JS 計時無法以 AppTest 覆蓋）

AppTest 不執行瀏覽器 JS，計時器實際「到點跳轉」與跨分頁同步**無法自動化**（同 auth-flow spike 精神，需親眼驗證）。開發時暫時把 `IDLE_TIMEOUT_SECONDS` 調小（如 10s）本機驗證：

- 開啟頁面靜置 → 到點自動導向登入頁 / mock 換回預設角色，且出現「因閒置逾 15 分鐘」提示。
- 靜置期間動滑鼠 / 按鍵 → 計時器重置，不登出。
- 兩分頁：A 持續操作、B 靜置 → B 不被踢出（localStorage `storage` 事件同步）。
- 手動點 TopBar 登出 → **即時**跳轉（無過場頁、不帶 idle 提示），確認 §7.2 手動路徑未被拖慢。

> **偵測粒度**：活動以 `IDLE_ACTIVITY_THROTTLE_SECONDS`（30s）節流，故實際登出時點相對「最後一次活動」有 ±節流秒數的誤差（15 分 ± 30s），屬預期。

### 8.4 提交前

- `pytest` 全綠（見 [CLAUDE.md 提交前檢查](../../CLAUDE.md)）。

---

## 9. 安全性與未決事項

### 9.1 安全性要點

- **訊號不等於已登出**：`?logout=1&reason=idle` 僅為攔截訊號，真正登出由 server 執行（同 logout.md §2.2）。
- **reason 不可信**：來自 query param，**僅供顯示**、以白名單收斂（§5.2），不參與安全判斷、不反射原始字串。
- **純前端的侷限（D2）**：JS 被停用 / 繞過時不生效，Streamlit 端不會閒置登出；此為刻意取捨，安全兜底回落到 BFF session 壽命與 introspection 401。
- **`ss_last_activity` 非敏感**：僅為 epoch 時間戳，可存 localStorage；**不得**放任何 token / 身分資訊。
- **不延長 BFF session**：Streamlit idle timeout 是額外控制，不覆寫 BFF 既有壽命。

### 9.2 未決 / 待確認

- [ ] **是否需伺服器端權威層**：目前純前端，JS 失效即不生效。若資安要求「保證」閒置登出，需另立規格補伺服器端兜底（本次刻意不做）。
- [ ] **與主前端 idle 政策一致性**（D3）：主前端 BFF 是否有各自 idle 逾時？兩者體感是否需對齊 / 上收至 BFF。
- [ ] **15 分是否可配置 / 依角色差異化**：目前全域 `IDLE_TIMEOUT_SECONDS=900`。
- [ ] **選配：登入頁原因參數**（§6.1）：是否請主前端支援 `?reason=session_timeout`，取代過場頁。

---

## 10. 相關文件

- [認證流程 §4.5 登出](auth-flow.md#45-登出)（BFF logout 契約、CSRF）
- [登出接線規格](logout.md)（`?logout=1` 訊號機制、AppTest 限制、spy 手法）
- [主題切換 §5](theme-toggle.md)（`components.html` JS 注入模式、`window.parent` 操作）
- [設定模組](config.md)（設定項與環境覆寫）
- `lib/auth.py::logout()`、`lib/state.py`、`app.py`（被延伸的既有實作）
