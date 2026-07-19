# 規格：ThemeToggle（日夜模式切換）

對齊 StreamSightFrontend `ThemeToggle.tsx` + `ThemeProvider.tsx` + `globals.css`。

TopBar 右側的圖示按鈕，切換 Streamlit 自訂 CSS 層的顯示主題（`dark` / `light`）。

> **目前狀態（2026-07）**：主題切換功能透過 `ENABLE_THEME_TOGGLE` 環境變數控制開關，
> 預設 `0`（關閉）。關閉時 icon 不渲染；開啟時 icon 顯示但點擊功能待實作（按鈕為 `disabled`）。
> 應用程式固定白天主題（`light`）。

> **範圍說明**：主題切換僅影響以 CSS 字面值撰寫的自訂樣式（TopBar、Sidebar Nav 等）；
> Streamlit 內建元件（按鈕、輸入框等）由 `config.toml` 控制，不隨之切換。

---

## 1. 對齊前端（目前實作狀態）

| 面向 | StreamSightFrontend | Streamlit（目前） |
|---|---|---|
| 元件 | `ThemeToggle.tsx` | `lib/topbar.py` + `lib/theme.py` |
| 預設主題 | flag off → `light`（硬編碼）；flag on → cookie，缺省 `dark`（見 §1.1） | `light`（暫時固定；見 §1.1） |
| 圖示邏輯 | `isLight` → 太陽；`!isLight` → 月亮 | 同（SVG 已實作，按 `theme` 參數選圖） |
| 按鈕狀態 | 可點擊 | `disabled`（功能待啟用） |
| `aria-pressed` | `isLight`（`"true"/"false"`） | 未使用（按鈕 disabled） |
| `aria-label` | `isLight ? '切換為深色' : '切換為淺色'` | 靜態 `"切換為深色"` |
| Cookie 名稱 | `theme` | `theme` |
| Cookie Max-Age | 31,536,000 秒（1 年） | 同 |
| Cookie SameSite | `Lax` | 同 |
| 未知值收斂 | `dark`（僅 flag on 的 cookie 解析路徑） | `light` |
| FOUC guard | `data-theme-ready` mount 後掛上 | 同（JS 注入後掛） |
| 過渡動畫 | 150ms ease（color / bg / border） | 同 |
| `prefers-reduced-motion` | `transition: none !important` | 同 |
| dark token 來源 | `globals.css` `@theme` | `main.css` `html[data-theme="dark"]` |
| light token 來源 | `globals.css` `html[data-theme="light"]` | `main.css`（現有字面值） |

### 1.1 預設主題解析（依 `ENABLE_THEME_TOGGLE`）

Frontend 於 `src/app/layout.tsx` 依 flag 分兩條路徑；未知 / 缺省值收斂見
`src/lib/theme/schema.ts` `parseTheme`（收斂到 `dark`）。

```typescript
// StreamSightFrontend/src/app/layout.tsx
const theme =
  process.env.NEXT_PUBLIC_ENABLE_THEME_TOGGLE === '1'
    ? await readThemeCookie()   // cookie 缺省 / 未知 → parseTheme 收斂 'dark'
    : 'light';                  // 切換關閉 → 硬編碼 light
```

| 情境 | StreamSightFrontend | Streamlit（目前） |
|---|---|---|
| flag 關閉（`!= '1'`，**目前預設**） | `'light'`（`layout.tsx` 硬編碼） | `'light'`（`init_theme_state` 固定） |
| flag 開啟、有 cookie | cookie 值（`'light'` / `'dark'`） | 待實作（目前仍固定 `'light'`） |
| flag 開啟、無 cookie / 未知值 | `'dark'`（`parseTheme` 收斂） | 待實作（目前仍固定 `'light'`） |

> **目前兩端一致**：`ENABLE_THEME_TOGGLE=0` 下 Frontend 與 Streamlit 皆渲染 `light`。
> 差異僅在「未來啟用切換」時浮現——屆時需決定 Streamlit 無 cookie 是否比照 Frontend
> 收斂到 `dark`（見 §6）。

---

## 2. 功能開關（`ENABLE_THEME_TOGGLE`）

`lib/config.py` `BaseAppSettings` 欄位：

```python
enable_theme_toggle: bool = False  # True → 顯示主題切換 icon；False → 隱藏（0/1）
```

`.env.example`：

```
# ENABLE_THEME_TOGGLE: 主題切換 icon 顯示開關；0=隱藏（預設）/ 1=顯示
ENABLE_THEME_TOGGLE=0
```

`app.py` 使用：

```python
render_topbar(actor, cms_base_url=_cms_url, theme=st.session_state["theme"],
              enable_theme_toggle=get_settings().enable_theme_toggle)
```

---

## 3. 圖示 SVG

`lib/topbar.py` 定義兩個常數（對齊 `ThemeToggle.tsx`）：

```
viewBox="0 0 24 24" / fill="none" / stroke="currentColor" / stroke-width="2" /
stroke-linecap="round" / stroke-linejoin="round" / aria-hidden="true" / width="18" height="18"
```

### 太陽（`_SUN_SVG`）— `theme="light"` 時顯示

```html
<circle cx="12" cy="12" r="5"/>
<line x1="12"    y1="1"     x2="12"    y2="3"/>
<line x1="12"    y1="21"    x2="12"    y2="23"/>
<line x1="4.22"  y1="4.22"  x2="5.64"  y2="5.64"/>
<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
<line x1="1"     y1="12"    x2="3"     y2="12"/>
<line x1="21"    y1="12"    x2="23"    y2="12"/>
<line x1="4.22"  y1="19.78" x2="5.64"  y2="18.36"/>
<line x1="18.36" y1="5.64"  x2="19.78" y2="4.22"/>
```

### 月亮（`_MOON_SVG`）— `theme="dark"` 時顯示

```html
<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
```

---

## 4. HTML 結構

`_build_topbar_html()` 接受 `theme: str = "light"` 與 `enable_theme_toggle: bool = False`。

```python
def _build_topbar_html(
    actor: Actor,
    cms_base_url: str = "",
    theme: str = "light",
    enable_theme_toggle: bool = False,
) -> str: ...
```

### `enable_theme_toggle=False`（預設）

按鈕完全不渲染（HTML 中無 `ss-topbar__theme-btn`）。

### `enable_theme_toggle=True`

```html
<!-- light mode（目前固定） -->
<button class="ss-topbar__theme-btn"
        type="button"
        disabled
        aria-label="切換為深色">
  <!-- _SUN_SVG -->
</button>
```

`disabled` 屬性使瀏覽器原生阻擋所有點擊事件；按鈕目前僅為視覺佔位。

---

## 5. 狀態管理

### 5.1 Python 側（`st.session_state`）

- 鍵名：`"theme"`；值：`"light"`（目前固定）。
- **初始化時機**：`app.py` 進入點，呼叫 `init_theme_state()`。
- 初始值：
  1. `st.session_state["theme"]` 已存在 → 沿用。
  2. 否則設預設值 `"light"`。
- `_build_topbar_html(actor, cms_base_url, theme, enable_theme_toggle)` 呼叫端傳入 `st.session_state["theme"]`。

### 5.2 Client 側（`data-theme`）

- `html[data-theme="light"]` attribute 由 JS 注入時設定（見 §6）。
- Cookie 僅保留結構；目前 JS 不讀 cookie 做判斷（固定 light）。

> **啟用切換後（§6.2）**：`data-theme` 與 cookie 改由 client-side JS 依使用者點擊即時更新，
> `st.session_state["theme"]` 不再反映 live 主題，僅作首屏 icon 的初始猜測（固定 `light`）。

---

## 6. JS 注入與切換邏輯

### 6.1 目前實作（停用態）

`lib/theme.py` 的 `_THEME_JS`，於 `app.py` 每次 rerun 經 `inject_theme_js()` 以
`streamlit.components.v1.components.html(height=0)` 注入。目前固定設 `data-theme="light"`
並掛上 FOUC guard，無 click handler：

```javascript
(function () {
  var pdoc = window.parent.document;
  pdoc.documentElement.dataset.theme = 'light';
  pdoc.documentElement.setAttribute('data-theme-ready', '');
})();
```

> 另有 `_FORCE_LIGHT_JS`（清 Streamlit `stActiveTheme*` localStorage、防重載迴圈），
> **與切換功能正交**：其職責是鎖定 Streamlit **內建元件**恆為 light（§11），啟用切換後
> 仍須保留（自訂 CSS 層才隨 `data-theme` 切換）。

---

### 6.2 啟用切換功能：完整可實作規格

> 本節將 §6.1 的「未來需恢復的邏輯」展開為可直接實作、可測試的規格。
> 觸發條件：`ENABLE_THEME_TOGGLE=1`。停用態（=0）行為不變。

#### 6.2.1 架構決策：純 client-side 切換，不繞回 Python

主題只影響**自訂 CSS 層**（`html[data-theme]`），該屬性掛在 **parent document**，
跨 rerun 不重載。Streamlit 無 client→Python 的 `session_state` 回寫通道（僅 `st.query_params`
可間接觸發 rerun），且主題切換不需要伺服器參與。因此對齊 Frontend 的做法：

| 方案 | 說明 | 採用 |
|---|---|---|
| **A. 純 client-side JS**（採用） | JS 讀 cookie → 設 `data-theme` → 寫 cookie → 換 icon / aria，全程不 rerun | ✅ |
| B. `query_params` 往返 | JS 改 URL → Python 讀 `st.query_params` → 寫 `session_state` → rerun 重繪 | ❌ 每次切換整頁 rerun + 閃爍，且主題純 CSS 無需伺服器 |

**推論**：`st.session_state["theme"]` 不再反映「使用者實際選的主題」——它只作為
**首屏伺服器渲染的初始 icon 猜測**（固定 `light`）；真正的 live 主題由 JS 依 cookie 決定。
此為刻意設計，需在 §5 標注。

#### 6.2.2 決策點 D1：未知 / 缺省 cookie 的收斂值

| 選項 | 值 | 後果 |
|---|---|---|
| **D1-a（建議）** | `light` | 沿用現有 `parse_theme`；與 config.toml 鎖定的 light 內建元件一致，不會出現「自訂層深色＋內建元件淺色」的半深狀態 |
| D1-b | `dark`（對齊 Frontend `parseTheme`） | 首次造訪即深色自訂層，但 Streamlit 內建元件（§11）仍是 light → 視覺割裂 |

> **建議採 D1-a（`light`）**。理由：Streamlit 內建元件受 config.toml `base="light"` 鎖定、
> 無法隨 `data-theme` 變暗；若無 cookie 就進深色，整站會呈半深割裂。此為與 Frontend
> **刻意的差異**（Frontend 全站可深色，故收斂 `dark`；Streamlit 內建層不能深色，故收斂 `light`）。
> 實作前請 confirm 此決策；下方 JS / 測試以 D1-a 撰寫。

#### 6.2.3 完整 JS（`_THEME_TOGGLE_JS`）

`inject_theme_js()` 依 `enable_theme_toggle` 分支：`False` → 注入 §6.1 的 `_THEME_JS`；
`True` → 注入下列腳本。SVG 常數與 `Secure` 片段由 Python 以 `json.dumps` / 條件字串填入
（`%SUN%` / `%MOON%` / `%SECURE%` 為 Python 端 format 佔位）：

```javascript
(function () {
  var pdoc = window.parent.document;
  var SUN = %SUN%, MOON = %MOON%;        // Python 以 json.dumps(_SUN_SVG/_MOON_SVG) 填入
  var SECURE = %SECURE%;                  // is_prod ? "; Secure" : ""

  // readTheme：讀 theme cookie，未知 / 缺省收斂 'light'（決策 D1-a）
  function readTheme() {
    var m = pdoc.cookie.match(/(?:^|;\s*)theme=(light|dark)(?:;|$)/);
    return m ? m[1] : 'light';
  }
  // applyTheme：設 data-theme + 寫 cookie（冪等）
  function applyTheme(t) {
    pdoc.documentElement.dataset.theme = t;
    pdoc.cookie = 'theme=' + t + '; Max-Age=31536000; Path=/; SameSite=Lax' + SECURE;
  }
  // syncButton：換 SVG、更新 aria-pressed / aria-label（對齊 Frontend isLight）
  function syncButton(btn, t) {
    var isLight = t === 'light';
    btn.setAttribute('aria-pressed', isLight ? 'true' : 'false');
    btn.setAttribute('aria-label', isLight ? '切換為深色' : '切換為淺色');
    btn.innerHTML = isLight ? SUN : MOON;
  }

  var current = readTheme();
  applyTheme(current);
  pdoc.documentElement.setAttribute('data-theme-ready', '');

  // 按鈕由 st.markdown 注入 parent DOM，且 components.html iframe 可能早於其掛載 →
  // 短輪詢尋找按鈕（≤10 幀），找到即同步並綁定。
  var tries = 0;
  (function bind() {
    var btn = pdoc.querySelector('.ss-topbar__theme-btn');
    if (!btn) { if (tries++ < 10) requestAnimationFrame(bind); return; }
    syncButton(btn, pdoc.documentElement.dataset.theme || current);
    // 每次 rerun 皆為「新按鈕元素」→ 用 per-element dataset 旗標防重複綁定（見下方註）
    if (!btn.dataset.ssThemeBound) {
      btn.dataset.ssThemeBound = '1';
      btn.addEventListener('click', function () {
        var next = (pdoc.documentElement.dataset.theme === 'dark') ? 'light' : 'dark';
        applyTheme(next);
        syncButton(pdoc.querySelector('.ss-topbar__theme-btn'), next);
      });
    }
  })();
})();
```

> **關鍵修正**：§6.1 舊表寫「`parent.__ssThemeReady` 全域旗標防重複註冊」——在 Streamlit
> rerun 模型下**錯誤**。每次 rerun `st.markdown` 產生**全新按鈕元素**，全域旗標會使新按鈕
> 拿不到監聽器。正解是 **per-element 旗標**（`btn.dataset.ssThemeBound`）：新按鈕綁一次、
> 同一按鈕不重綁。

#### 6.2.4 `lib/topbar.py` 變更

`_build_topbar_html` 在 `enable_theme_toggle=True` 時產生**可互動**按鈕（移除 `disabled`）：

```html
<!-- 初始伺服器渲染：以 light 為預設猜測；JS 於載入時依 cookie 校正 -->
<button class="ss-topbar__theme-btn"
        type="button"
        aria-pressed="true"
        aria-label="切換為深色">
  <!-- _SUN_SVG（初始猜測；cookie=dark 時 JS 換成月亮） -->
</button>
```

- 移除 `disabled`；`aria-pressed`／`aria-label` 給**初始值**（light），交由 JS `syncButton` 校正。
- icon 初始為 `_SUN_SVG`（light 猜測）。`theme` 參數可續傳但僅為初始猜測，不再是事實來源。

#### 6.2.5 `lib/config.py` / `app.py` / `.env`

- `config.py`、`.env.example`：`enable_theme_toggle` 欄位已存在，無需變更。
- `app.py`：`inject_theme_js()` 需能取得 `enable_theme_toggle` 與 `is_prod`，例如
  `inject_theme_js(enable_theme_toggle=get_settings().enable_theme_toggle, is_prod=get_settings().app_env == "production")`。
- `render_topbar(...)` 已傳 `enable_theme_toggle`（§9），無需變更。

#### 6.2.6 CSS 變更（`styles/main.css`）

以 `:disabled` 區分「停用佔位」與「可互動」兩態，避免 CSS 需感知 flag：

```css
/* 可互動預設（enable_theme_toggle=1，按鈕無 disabled） */
.ss-topbar__theme-btn { cursor: pointer; opacity: 1; }
.ss-topbar__theme-btn:hover:not(:disabled) {
    color: #0f172a;                    /* ink-AAA */
    background: rgba(15, 23, 42, 0.12); /* line */
}
/* 停用佔位（enable_theme_toggle=0 開發預覽時的 disabled 按鈕） */
.ss-topbar__theme-btn:disabled { cursor: default; opacity: 0.6; }

/* 深色主題 hover 覆寫 */
html[data-theme="dark"] .ss-topbar__theme-btn:hover:not(:disabled) {
    color: rgba(230, 237, 246, 0.95);   /* ink-AAA */
    background: rgba(230, 237, 246, 0.08);
}
```

#### 6.2.7 首屏 icon 閃爍（已知取捨）

伺服器以 light 猜測渲染 icon；若 cookie=`dark`，JS 載入後把太陽換月亮，會有一次
極短 icon 閃爍。**完全消除**需伺服器端讀 cookie（§11 明確排除）。`data-theme` 由 JS 儘早套用，
色彩層閃爍已由 FOUC guard（§7.5）緩解；icon 閃爍列為**可接受的已知限制**。

#### 6.2.8 對齊 Frontend 對照（啟用後）

| 面向 | Frontend | Streamlit（啟用後） |
|---|---|---|
| 切換觸發 | `onClick={toggle}`（React） | `addEventListener('click')`（parent DOM 按鈕） |
| 主題翻轉 | `theme==='dark' ? 'light' : 'dark'` | 同（讀 `data-theme` 翻轉） |
| DOM 套用 | `documentElement.dataset.theme = next` | 同（透過 `window.parent.document`） |
| cookie 寫入 | `buildThemeCookieString(next, isProd)` | JS 內聯，字串格式相同（Max-Age/Path/SameSite/Secure） |
| aria 同步 | `aria-pressed={isLight}` / 動態 label | `syncButton` 設相同值 |
| 重複綁定防護 | React 單一 handler | per-element `dataset.ssThemeBound` |
| 未知值收斂 | `dark` | `light`（決策 D1-a；刻意差異） |
| 內建元件 | 全站隨主題 | 恆 light（`base="light"` 鎖定，§11） |

#### 6.2.9 測試規格（TDD，先寫失敗測試）

**`tests/unit/test_topbar.py`**（啟用態按鈕，先 RED）
```python
def test_theme_btn_interactive_when_toggle_enabled(actor):
    """enable_theme_toggle=True → 按鈕不含 disabled。"""
    html = _build_topbar_html(actor, enable_theme_toggle=True)
    assert "ss-topbar__theme-btn" in html
    # 只檢查按鈕片段內無 disabled（避免誤中其他元素）
    btn = html.split('ss-topbar__theme-btn', 1)[1].split("</button>", 1)[0]
    assert "disabled" not in btn

def test_theme_btn_has_aria_pressed(actor):
    html = _build_topbar_html(actor, enable_theme_toggle=True)
    assert 'aria-pressed="true"' in html   # 初始 light 猜測
```

**`tests/unit/test_theme.py`**（切換 JS 字串，仿現有 `_FORCE_LIGHT_JS` 測法）
```python
def test_toggle_js_reads_theme_cookie():        # 含讀 cookie 的 regex/字樣
def test_toggle_js_registers_click_listener():  # 含 addEventListener('click'
def test_toggle_js_guards_duplicate_binding():  # 含 ssThemeBound（per-element 旗標）
def test_toggle_js_cookie_has_max_age():         # 含 Max-Age=31536000
def test_toggle_js_no_secure_in_dev():           # is_prod=False → 不含 '; Secure'
def test_toggle_js_has_secure_in_prod():         # is_prod=True  → 含 '; Secure'
def test_toggle_js_default_converges_light():    # readTheme fallback 為 'light'（D1-a）
def test_inject_theme_js_uses_force_js_when_disabled():  # 停用態仍走 _THEME_JS + _FORCE_LIGHT_JS
```

> JS 為字串常數，比照現有 `test_force_light_js_*` 以「子字串斷言」驗證關鍵操作存在；
> 端到端點擊行為（DOM/cookie 真的變）建議另以 Playwright/瀏覽器煙霧測試涵蓋（非 pytest 範圍）。

#### 6.2.10 驗收清單

- [ ] D1 收斂值已 confirm（預設 D1-a=`light`）。
- [ ] `ENABLE_THEME_TOGGLE=1` 時按鈕可點，點擊即時切換 `data-theme`、無整頁 rerun。
- [ ] 重整後主題依 cookie 還原；未知/無 cookie → light。
- [ ] `aria-pressed`／`aria-label`／icon 三者與當前主題一致。
- [ ] 深色下 TopBar／Sidebar（§7.2–7.4）色彩正確；Streamlit 內建元件維持 light。
- [ ] 連續 rerun（如切頁、表單）後按鈕仍可點且只綁一個 handler。
- [ ] `ENABLE_THEME_TOGGLE=0` 行為與現況完全一致（回歸）。
- [ ] 新增測試全綠，既有 `test_force_light_js_*` / `test_parse_theme_*` 不破。

---

## 7. CSS 規格

### 7.1 ThemeToggle 按鈕（`ENABLE_THEME_TOGGLE=1` 時生效）

```css
/* disabled 狀態：cursor:default，opacity 表達非互動 */
.ss-topbar__theme-btn {
    width: 36px;
    height: 36px;
    border-radius: 6px;
    padding: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: rgba(15, 23, 42, 0.66);  /* ink-AA */
    background: transparent;
    border: none;
    cursor: default;
    flex-shrink: 0;
    opacity: 0.6;
}
```

### 7.2 深色主題覆寫（TopBar）

```css
html[data-theme="dark"] .ss-topbar__theme-btn {
    color: rgba(230, 237, 246, 0.45);  /* ink-A（停用態偏暗） */
}
```

### 7.3 深色主題覆寫（TopBar 整體）

見 `styles/main.css` `html[data-theme="dark"]` 區塊（對齊 Frontend `globals.css @theme dark base`）：

- `ss-topbar`：`background-color: #151c2b`（surface-card）、`border-bottom-color: rgba(230,237,246,0.12)`
- `ss-topbar__brand`：`rgba(230,237,246,0.95)`（ink-AAA）
- `ss-topbar__sysitem`（非 active）：`rgba(230,237,246,0.72)`（ink-AA），hover `bg: rgba(230,237,246,0.08)`
- `ss-topbar__sysitem--active`：`rgba(34,211,238,0.14)` 底 + `#22d3ee` 字
- `ss-topbar__accent`：`#22d3ee`
- `ss-topbar__username`：`rgba(230,237,246,0.45)`（ink-A）

### 7.4 深色主題覆寫（Sidebar Nav）

見 `styles/main.css` Sidebar Nav 深色覆寫區塊：

- 側欄背景：`#151c2b`（surface-card）
- 文字 cascade：`section[data-testid="stSidebar"] { color: rgba(230,237,246,0.72) }`
- 非 active 連結：`rgba(230,237,246,0.72)`
- hover：`bg rgba(230,237,246,0.08)`
- active：`bg rgba(230,237,246,0.14)`，字 `rgba(230,237,246,0.95)`，`p, span` 明確覆寫（對抗 Streamlit 優先注入）

### 7.5 FOUC Guard + 平滑過渡

```css
html[data-theme-ready],
html[data-theme-ready] * {
    transition-property: color, background-color, border-color;
    transition-duration: 150ms;
    transition-timing-function: ease;
}

@media (prefers-reduced-motion: reduce) {
    html[data-theme-ready],
    html[data-theme-ready] * { transition: none !important; }
}
```

### 7.6 主內容區深色覆寫（2026-07-19 起）

深色不再只蓋 TopBar / Sidebar——主內容區以 CSS 字面值對齊 Frontend `@theme` 深色 token
（`styles/main.css`「主內容區（Main）」區塊）：

> **文字類規則的 scope 用 `.stApp` 而非 `stMain`**：`st.dialog` 為 portal 不在
> `stMain` 下，側欄 dev switcher 的 label 亦需涵蓋。僅連結與 hr 維持 `stMain`
> scope（放寬會誤染 Sidebar Nav 連結色）。另注意兩個結構性陷阱（本輪實際踩過）：
> ① Streamlit 對 label / nav link / selectbox 值的**內層 p/span/div** 設明確
> textColor，僅靠外層繼承蓋不過，需明列內層；② 深色規則彼此的**特異度**要對齊
> （如 active 需 ≥ inactive），值寫對仍會被蓋掉。

| 對象 | 深色值（token） |
|---|---|
| `.stApp` 頁面底 / 文字 cascade | `#0b0f17`（surface-page）/ ink-AAA |
| `.stApp` h1–h6、Markdown p/li、widget label（含內層 p/span） | ink-AAA `rgba(230,237,246,.95)` |
| caption | ink-A `rgba(230,237,246,.45)` |
| 連結（stMain / dialog） | `#38bdf8`（ink-link） |
| hr / expander / table / st.form 邊框 | line `rgba(230,237,246,.12)` |
| `stMetric` 卡片 | `#151c2b`（surface-card）＋ label ink-AA / value ink-AAA |
| 次要按鈕 / form 送出鈕 / download 鈕 / uploader 內按鈕 | surface-card 底＋line 框＋ink-AAA 字；hover brand `#22d3ee` |
| 主要按鈕 | brand `#22d3ee` 底＋ink-on-brand `#06121a` 字；hover brand-400 `#38bdf8` |
| 輸入框（BaseWeb input/textarea/select） | surface-card 底＋line 框＋ink-AAA 字；placeholder ink-A；**內層 base-input/input 需透明化**（自帶白底）；focus 邊框 brand |
| selectbox 顯示值（內層 div） | ink-AAA |
| selectbox 下拉（popover listbox）/ date_input 日曆 | surface-card 底；option hover nav-hover |
| `st.dialog` 面板 | surface-card 底＋line 框；Close 鈕 ink-AA |
| `st.toast` | surface-card 底＋ink-AAA 字＋line 框 |
| slider | thumb 值 / thumb brand `#22d3ee`；刻度 ink-A |
| number_input 步進鈕 | surface-card 底＋ink-AA 字 |
| 檔案上傳 dropzone（含說明文字） | surface-card 底＋ink-AA 字 |
| tabs active / highlight | brand `#22d3ee`；tab-border line |
| dataframe 懸浮工具列 | surface-card 底＋ink-AA |
| vega-lite 圖表軸 / 圖例文字 | ink-AA（best-effort，CSS `fill` 蓋 SVG attribute） |

字體則由 `config.toml` `font = "PingFang TC, Noto Sans TC, system-ui, sans-serif"`
對齊 Frontend `--font-sans`（兩主題共用，Streamlit ≥1.46 支援自訂 stack）。

**已知限制**：canvas 渲染元件（`st.dataframe` glide-data-grid、圖表**圖面本體**）無法
以 CSS 覆寫，維持 light（軸文字已 best-effort 覆寫）；語義 alert（success/error/
warning/info）沿用 Streamlit 配色；`config.toml` `base="light"` 不變（§11），
未列於上表的元件內部仍為 light。
⚠ 本節大量使用 `data-testid` / `data-baseweb` 選擇器，Streamlit 升版需回歸。

---

## 8. Cookie 規格

`lib/theme.py` 的 `build_theme_cookie_string()`（對齊 Frontend `schema.ts`）：

| 屬性 | 值 |
|---|---|
| 名稱 | `theme` |
| 允許值 | `"light"` / `"dark"` |
| Max-Age | 31,536,000 秒（1 年） |
| Path | `/` |
| SameSite | `Lax` |
| Secure | 生產環境加（`APP_ENV == production`） |
| 未知值 / 缺省 | 收斂到 `"light"` |

```python
def parse_theme(raw: str | None) -> str:
    """未知 / 缺省值收斂到 'light'（應用程式預設白天主題）。"""
    return raw if raw in ("light", "dark") else "light"
```

---

## 9. 變更範圍

| 檔案 | 說明 |
|---|---|
| `lib/config.py` | `BaseAppSettings` 新增 `enable_theme_toggle: bool = False` |
| `lib/topbar.py` | `_build_topbar_html` / `render_topbar` 加 `enable_theme_toggle` 參數；`disabled` 按鈕；`_SUN_SVG` / `_MOON_SVG` 常數保留（icon 依 `theme` 選擇） |
| `lib/theme.py` | `parse_theme` / `init_theme_state` 預設改 `"light"`；`_THEME_JS` 簡化為固定 light；`inject_theme_js()` 保留 |
| `app.py` | `render_topbar` 傳入 `enable_theme_toggle=get_settings().enable_theme_toggle` |
| `styles/main.css` | `theme-btn`：`cursor:default; opacity:0.6`（disabled 視覺）；深色 TopBar / Sidebar / FOUC 已完整實作 |
| `.env.example` | 新增 `ENABLE_THEME_TOGGLE=0` |

### `app.py` 呼叫順序

```python
load_css()           # ② 載入 CSS
init_theme_state()   # ②′ theme session_state 初始化（預設 'light'）
init_logging()       # ②″

actor = resolve_actor()  # ③
...
render_topbar(actor, cms_base_url=_cms_url, theme=st.session_state["theme"],
              enable_theme_toggle=get_settings().enable_theme_toggle)  # ⑥
inject_theme_js()    # ⑦ 固定設 data-theme=light
```

---

## 10. 測試規格

### 10.1 `tests/unit/test_config.py`

```python
def test_enable_theme_toggle_defaults_false():
    """ENABLE_THEME_TOGGLE 預設 False。"""
    assert get_settings().enable_theme_toggle is False

def test_enable_theme_toggle_can_be_set_true(monkeypatch):
    """ENABLE_THEME_TOGGLE=1 → True。"""
    monkeypatch.setenv("ENABLE_THEME_TOGGLE", "1")
    assert get_settings().enable_theme_toggle is True
```

### 10.2 `tests/unit/test_topbar.py` ThemeToggle 相關測試

```python
def test_theme_btn_hidden_when_toggle_disabled(actor):
    """ENABLE_THEME_TOGGLE=False → icon 不渲染。"""
    html = _build_topbar_html(actor, enable_theme_toggle=False)
    assert "ss-topbar__theme-btn" not in html

def test_theme_btn_shown_when_toggle_enabled(actor):
    """ENABLE_THEME_TOGGLE=True → icon 出現。"""
    html = _build_topbar_html(actor, enable_theme_toggle=True)
    assert "ss-topbar__theme-btn" in html
```

### 10.3 `tests/unit/test_theme.py` parse_theme 測試

```python
def test_parse_theme_dark():    assert parse_theme("dark") == "dark"
def test_parse_theme_light():   assert parse_theme("light") == "light"
def test_parse_theme_none():    assert parse_theme(None) == "light"     # 收斂到 light
def test_parse_theme_unknown(): assert parse_theme("system") == "light"
def test_parse_theme_empty():   assert parse_theme("") == "light"
```

---

## 11. 不在本規格範圍

- Streamlit 內建元件的**底層主題**切換——`config.toml` 不支援執行期切換。
  常用元件的基礎表面（按鈕、輸入框、metric、tabs、uploader 等）已由 §7.6 的 CSS
  覆寫跟隨切換；canvas 類（dataframe、圖表）與語義 alert 仍不隨。
- 瀏覽器端 `prefers-color-scheme` 媒體查詢偵測（自動跟隨系統主題）。**且已明確排除**：
  `config.toml` 以 `base = "light"` 鎖定白天模式，避免 Streamlit 底層元件在深色
  系統偏好下自動變暗（見 design-system.md §主題設定）。
- 伺服器端 Python 讀取 cookie。
- ThemeToggle 以外的 TopBar 互動（登出按鈕 BFF 流程）。

---

## 12. 相關文件

- [設計系統規格](design-system.md)
- [TopBar CMS 連結規格](topbar-cms-link.md)
- StreamSightFrontend `src/components/ui/ThemeToggle.tsx`
- StreamSightFrontend `src/lib/theme/ThemeProvider.tsx`
- StreamSightFrontend `src/app/globals.css`
- StreamSightFrontend `src/lib/theme/schema.ts`
