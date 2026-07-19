# 規格：ThemeToggle（日夜模式切換）

對齊 StreamSightFrontend `ThemeToggle.tsx` + `ThemeProvider.tsx` + `globals.css`。

TopBar 右側的圖示按鈕，切換 Streamlit 自訂 CSS 層的顯示主題（`dark` / `light`）。

> **範圍說明**：主題切換僅影響以 CSS 字面值撰寫的自訂樣式（TopBar、Sidebar Nav 等）；Streamlit 內建元件（按鈕、輸入框等）由 `config.toml` 控制，不隨之切換。

---

## 1. 對齊前端

| 面向 | StreamSightFrontend | Streamlit |
|---|---|---|
| 元件 | `ThemeToggle.tsx` | `lib/topbar.py` + `lib/theme.py` |
| 預設主題 | `dark` | `dark` |
| 圖示邏輯 | `isLight` → 太陽；`!isLight` → 月亮 | 同 |
| `aria-pressed` | `isLight`（boolean → 字串 `"true"/"false"`） | 同 |
| `aria-label` | `isLight ? '切換為深色' : '切換為淺色'` | 同 |
| Cookie 名稱 | `theme` | `theme` |
| Cookie Max-Age | 31,536,000 秒（1 年） | 同 |
| Cookie SameSite | `Lax` | 同 |
| 未知值收斂 | `dark` | `dark` |
| FOUC guard | `data-theme-ready` mount 後掛上 | 同（JS 注入後掛） |
| 過渡動畫 | 150ms ease（color / bg / border） | 同 |
| `prefers-reduced-motion` | `transition: none !important` | 同 |
| dark token 來源 | `globals.css` `@theme` | `main.css` `html[data-theme="dark"]` |
| light token 來源 | `globals.css` `html[data-theme="light"]` | `main.css`（現有字面值） |

---

## 2. 圖示 SVG

兩個圖示的 SVG 屬性完全對齊 `ThemeToggle.tsx`：
`viewBox="0 0 24 24"` / `fill="none"` / `stroke="currentColor"` / `stroke-width="2"` /
`stroke-linecap="round"` / `stroke-linejoin="round"` / `aria-hidden="true"` / `width="20" height="20"`。

### 太陽（`_SUN_SVG`）— 目前為 **light mode**，點擊切深色

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

### 月亮（`_MOON_SVG`）— 目前為 **dark mode**，點擊切淺色

```html
<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
```

> `_SUN_SVG` 已在 `lib/topbar.py` 實作（對齊前端）；`_MOON_SVG` 為新增。

---

## 3. HTML 結構與 aria 屬性

`_build_topbar_html()` 須接受 `theme: str` 參數（預設 `"dark"`），依值選擇圖示與 aria 屬性。

```html
<!-- dark mode（預設） -->
<button class="ss-topbar__theme-btn"
        type="button"
        aria-pressed="false"
        aria-label="切換為淺色">
  <!-- _MOON_SVG -->
</button>

<!-- light mode -->
<button class="ss-topbar__theme-btn"
        type="button"
        aria-pressed="true"
        aria-label="切換為深色">
  <!-- _SUN_SVG -->
</button>
```

**`aria-pressed` 語意**：`true` = 目前處於「已按下 / 淺色啟用」狀態；`false` = 深色啟用。對齊前端 `aria-pressed={isLight}`。

---

## 4. 狀態管理

### 4.1 Python 側（`st.session_state`）

- 鍵名：`"theme"`；值：`"dark"` | `"light"`。
- **初始化時機**：`app.py` 進入點，呼叫 `init_theme_state()`（新增於 `lib/theme.py`）。
- 初始值決定順序：
  1. `st.session_state["theme"]` 已存在 → 沿用（同一 Python session 重跑時不重置）。
  2. 否則設預設值 `"dark"`。
- `_build_topbar_html(actor, cms_base_url, theme)` 呼叫端傳入 `st.session_state["theme"]`。

### 4.2 Client 側（cookie + `data-theme`）

- Cookie `theme` 存活期 1 年，作為跨 session 持久化。
- `html[data-theme="dark|light"]` attribute 控制 CSS cascade。
- JS 注入（見 §5）負責讀 cookie → 套用 `data-theme` → 處理點擊 → 寫 cookie。

### 4.3 Python 與 Client 側不同步的情況

| 事件 | 結果 | 說明 |
|---|---|---|
| 同一 session 內切換後，其他 widget 觸發 rerun | 一致 | `st.session_state["theme"]` 已更新（JS 無需 sync back） |
| 瀏覽器重新整理（新 Python session） | 短暫 flash | 初始 HTML 以 `dark` 渲染；JS 讀 cookie 修正（< 50ms） |
| 使用者從未切換（cookie 不存在） | 一致 | Python default `dark` = JS default `dark` |

**Flash 緩解**：JS 一進 DOM 立即讀 cookie，在 `DOMContentLoaded` 前套用 `data-theme`；
HTML 按鈕初始以 `dark` 渲染，JS 在需要時同步更新 SVG 與 aria 屬性。

---

## 5. 互動機制（Streamlit 限制與純 JS 方案）

### 5.1 限制

`st.markdown(unsafe_allow_html=True)` 渲染的 HTML 元素無法觸發 Python callback；
`st.components.v1.html()` 以 sandbox iframe 執行，但 Streamlit 元件 iframe 與主頁面**同源**，
可存取 `window.parent.document`。

### 5.2 方案：JS 注入（`inject_theme_js()`）

在 `lib/theme.py` 新增 `inject_theme_js()` 函式，於 `app.py` 進入點每次 rerun 均呼叫（`st.components.v1.html()` 每次 rerun 重執行，JS 本身設計為冪等）。

#### 冪等設計原則

| 操作 | 冪等策略 |
|---|---|
| `applyTheme()` — 套用 `data-theme`、寫 cookie | 每次 rerun 均執行，結果相同無副作用 |
| `syncButton()` — 換 SVG、更新 aria | 每次 rerun 均執行，修正 Python 初始渲染與 cookie 狀態不符的短暫 flash |
| `enableTransition()` — 掛 `data-theme-ready` | 屬性已存在時 `setAttribute` 為 no-op |
| click 監聽器 | `parent.__ssThemeReady` 旗標防止重複註冊（每 session 只加一次） |

```javascript
(function () {
  const COOKIE = 'theme';
  const MAX_AGE = 31536000;
  const par = window.parent;
  const pdoc = par.document;

  // SVG 路徑常數（與 lib/topbar.py _SUN_SVG / _MOON_SVG 完全對齊）
  const SUN_INNER = [
    '<circle cx="12" cy="12" r="5"/>',
    '<line x1="12" y1="1" x2="12" y2="3"/>',
    '<line x1="12" y1="21" x2="12" y2="23"/>',
    '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>',
    '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>',
    '<line x1="1" y1="12" x2="3" y2="12"/>',
    '<line x1="21" y1="12" x2="23" y2="12"/>',
    '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>',
    '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>',
  ].join('');
  const MOON_INNER = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';

  // 1. 讀 cookie，未知值收斂到 "dark"
  function readCookie() {
    const m = pdoc.cookie.match(/(?:^|;\s*)theme=([^;]+)/);
    return m && (m[1] === 'light' || m[1] === 'dark') ? m[1] : 'dark';
  }

  // 2. 套用 data-theme + 寫 cookie（冪等）
  function applyTheme(theme) {
    pdoc.documentElement.dataset.theme = theme;
    pdoc.cookie = COOKIE + '=' + theme + '; Max-Age=' + MAX_AGE + '; Path=/; SameSite=Lax';
  }

  // 3. FOUC guard（setAttribute 對已存在屬性為 no-op）
  function enableTransition() {
    pdoc.documentElement.setAttribute('data-theme-ready', '');
  }

  // 4. 同步按鈕 SVG + aria（修正 Python 初始渲染 flash；每次 rerun 均執行）
  function syncButton(theme) {
    const btn = pdoc.querySelector('.ss-topbar__theme-btn');
    if (!btn) return;
    const isLight = theme === 'light';
    btn.setAttribute('aria-pressed', String(isLight));
    btn.setAttribute('aria-label', isLight ? '切換為深色' : '切換為淺色');
    const svg = btn.querySelector('svg');
    if (svg) svg.innerHTML = isLight ? SUN_INNER : MOON_INNER;
  }

  // 5. 初始化（每次 rerun 均執行）
  const initial = readCookie();
  applyTheme(initial);
  syncButton(initial);
  enableTransition();

  // 6. 點擊監聽器：parent.__ssThemeReady 旗標確保整個 session 只加一次
  if (!par.__ssThemeReady) {
    par.__ssThemeReady = true;
    pdoc.addEventListener('click', function (e) {
      const btn = e.target.closest('.ss-topbar__theme-btn');
      if (!btn) return;
      const current = pdoc.documentElement.dataset.theme || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      syncButton(next);
    });
  }
})();
```

---

## 6. CSS 規格

### 6.1 現有樣式（已對齊，無需修改）

```css
/* ThemeToggle：w-9(36px) h-9(36px) rounded-md(6px) */
.ss-topbar__theme-btn { ... }
.ss-topbar__theme-btn:hover { ... }
```

對齊前端 `ThemeToggle.tsx` class：
`w-9 h-9 rounded-md text-ink-AA hover:text-ink-AAA hover:bg-line transition-colors`。

### 6.2 新增：深色主題 token 覆寫

在 `main.css` 新增 `html[data-theme="dark"]` 區塊，對齊 Frontend `globals.css` `@theme`（dark base）。
特異度規則：`html[data-theme="dark"] .class`（0,2,0）> 現有單類選擇器規則（0,1,0）；
`html[data-theme="dark"] [attr]`（0,2,1）> Streamlit 自身注入的元素規則（通常 0,1,0）。

#### 6.2.1 TopBar 深色覆寫

```css
/* ============================================================
 * TopBar 深色覆寫（對齊 Frontend globals.css @theme dark base）
 * ============================================================ */
html[data-theme="dark"] .ss-topbar {
  background-color: #151c2b;                       /* surface-card */
  border-bottom-color: rgba(230, 237, 246, 0.12);  /* line */
}

html[data-theme="dark"] .ss-topbar__brand,
html[data-theme="dark"] .ss-topbar__brand:hover,
html[data-theme="dark"] .ss-topbar__brand:visited,
html[data-theme="dark"] .ss-topbar__sysitem,
html[data-theme="dark"] .ss-topbar__sysitem:hover {
  color: rgba(230, 237, 246, 0.95);                /* ink-AAA */
  text-decoration: none;
}

html[data-theme="dark"] .ss-topbar__sysitem--active,
html[data-theme="dark"] .ss-topbar__sysitem--active:hover {
  background-color: rgba(34, 211, 238, 0.14);      /* brand-overlay（cyan） */
  color: #22d3ee;                                  /* brand */
}

html[data-theme="dark"] .ss-topbar__accent {
  color: #22d3ee;                                  /* brand */
}

html[data-theme="dark"] .ss-topbar__username {
  color: rgba(230, 237, 246, 0.45);                /* ink-A */
}

html[data-theme="dark"] .ss-topbar__theme-btn {
  color: rgba(230, 237, 246, 0.72);                /* ink-AA */
}

html[data-theme="dark"] .ss-topbar__theme-btn:hover {
  color: rgba(230, 237, 246, 0.95);                /* ink-AAA */
  background-color: rgba(230, 237, 246, 0.12);     /* line */
}
```

#### 6.2.2 Sidebar Nav 深色覆寫

對齊 Frontend `globals.css` `@theme`（dark base）nav token，
覆寫 `main.css` 現有側欄 CSS 的淺色字面值。
Streamlit 的側欄背景來自 `config.toml secondaryBackgroundColor`（`#f1f5f9`），
需以較高特異度選擇器覆蓋。

```css
/* ============================================================
 * Sidebar Nav 深色覆寫（對齊 Frontend globals.css @theme dark base）
 * ============================================================ */

/* 側欄背景：config.toml #f1f5f9 → surface-card #151c2b */
html[data-theme="dark"] section[data-testid="stSidebar"] > div {
  background-color: #151c2b;
}

/* Nav 連結基底文字：ink-AA dark */
html[data-theme="dark"] [data-testid="stSidebarNavLink"] {
  color: rgba(230, 237, 246, 0.72);                /* ink-AA */
}

/* hover：nav-hover dark */
html[data-theme="dark"] [data-testid="stSidebarNavLink"]:hover {
  background-color: rgba(230, 237, 246, 0.08);     /* nav-hover */
  color: rgba(230, 237, 246, 0.72);
}

/* active：nav-active dark + ink-AAA dark */
html[data-theme="dark"] [data-testid="stSidebarNavLink"][aria-current="page"] {
  background-color: rgba(230, 237, 246, 0.14);     /* nav-active */
  color: rgba(230, 237, 246, 0.95);                /* ink-AAA */
}

/* 收合按鈕 */
html[data-theme="dark"] [data-testid="stSidebarCollapseButton"] button {
  color: rgba(230, 237, 246, 0.72);                /* ink-AA */
}

html[data-theme="dark"] [data-testid="stSidebarCollapseButton"] button:hover {
  background-color: rgba(230, 237, 246, 0.08);     /* nav-hover */
}

/* 調寬把手 hover 細線：brand dark（cyan） */
html[data-theme="dark"] [data-testid="stSidebarResizeHandle"]:hover::after {
  background-color: #22d3ee;                       /* brand */
}
```

### 6.3 新增：FOUC Guard + 平滑過渡

對齊 Frontend `globals.css` spec 014b §3.4。

```css
/* ============================================================
 * FOUC Guard + 平滑過渡（對齊 Frontend globals.css 014b §3.4）
 * transition 僅在 JS 掛上 [data-theme-ready] 後啟用，
 * 避免首屏初始色觸發過渡動畫。
 * ============================================================ */
html[data-theme-ready],
html[data-theme-ready] * {
  transition-property: color, background-color, border-color;
  transition-duration: 150ms;
  transition-timing-function: ease;
}

@media (prefers-reduced-motion: reduce) {
  html[data-theme-ready],
  html[data-theme-ready] * {
    transition: none !important;
  }
}
```

---

## 7. Cookie 規格

對齊 Frontend `lib/theme/schema.ts`。

| 屬性 | 值 |
|---|---|
| 名稱 | `theme` |
| 允許值 | `"light"` / `"dark"` |
| Max-Age | 31,536,000 秒（1 年） |
| Path | `/` |
| SameSite | `Lax` |
| Secure | 生產環境加（`NODE_ENV === "production"` → Python: `APP_ENV != "local"`） |
| 未知值 / 缺省 | 收斂到 `"dark"` |

`lib/theme.py` 新增純函式（對齊 Frontend schema.ts）：

```python
THEME_COOKIE = "theme"
THEME_COOKIE_MAX_AGE = 31_536_000  # 1 year

def parse_theme(raw: str | None) -> str:
    """未知 / 缺省值收斂到 'dark'。"""
    return raw if raw in ("light", "dark") else "dark"

def build_theme_cookie_string(theme: str, is_prod: bool = False) -> str:
    """組裝 cookie 字串（純函式，便於單元測試）。"""
    secure = "; Secure" if is_prod else ""
    return f"{THEME_COOKIE}={theme}; Max-Age={THEME_COOKIE_MAX_AGE}; Path=/; SameSite=Lax{secure}"
```

---

## 8. 變更範圍

| 檔案 | 變更說明 |
|---|---|
| `lib/topbar.py` | 新增 `_MOON_SVG`；`_build_topbar_html()` 加 `theme: str = "dark"` 參數；`render_topbar()` 同步加 `theme` 參數並往下傳 |
| `lib/theme.py` | 新增 `THEME_COOKIE`、`THEME_COOKIE_MAX_AGE`、`parse_theme()`、`build_theme_cookie_string()`、`_THEME_JS`（模組層常數）、`inject_theme_js()`、`init_theme_state()` |
| `app.py` | 進入點 load_css 後呼叫 `init_theme_state()`；`render_topbar()` 傳入 `theme=st.session_state["theme"]`；render_topbar 之後呼叫 `inject_theme_js()` |
| `styles/main.css` | 新增 §6.2.1 TopBar 深色覆寫、§6.2.2 Sidebar Nav 深色覆寫、§6.3 FOUC guard + 過渡 CSS |
| `tests/unit/test_topbar.py` | 新增 ThemeToggle 多主題測試（§9.1）；更新現有 2 個測試（§10） |
| `tests/unit/test_theme.py` | 新增檔案：`parse_theme()` / `build_theme_cookie_string()` 單元測試（§9.2） |

### `lib/topbar.py` 關鍵片段

```python
_MOON_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" \
fill="none" stroke="currentColor" stroke-width="2" \
stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">\
<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>\
</svg>"""


def _build_topbar_html(actor: Actor, cms_base_url: str = "", theme: str = "dark") -> str:
    is_light = theme == "light"
    svg = _SUN_SVG if is_light else _MOON_SVG
    aria_pressed = "true" if is_light else "false"
    aria_label = "切換為深色" if is_light else "切換為淺色"
    # ... 其餘組裝邏輯不變 ...
    f'<button class="ss-topbar__theme-btn" type="button" '
    f'aria-pressed="{aria_pressed}" aria-label="{aria_label}">'
    f"{svg}</button>"


def render_topbar(actor: Actor, cms_base_url: str = "", theme: str = "dark") -> None:
    """TopBar 注入頁面頂端。theme 參數由呼叫端傳入 st.session_state['theme']。"""
    st.markdown(_build_topbar_html(actor, cms_base_url, theme), unsafe_allow_html=True)
```

### `lib/theme.py` 新增結構

```python
THEME_COOKIE = "theme"
THEME_COOKIE_MAX_AGE = 31_536_000  # 1 year

_THEME_JS: str = """..."""  # §5.2 完整 JS（模組層常數，避免 inject 時重複建構字串）


def parse_theme(raw: str | None) -> str: ...
def build_theme_cookie_string(theme: str, is_prod: bool = False) -> str: ...

def init_theme_state() -> None:
    """session_state["theme"] 初始化（首次 session 設預設值 'dark'）。"""
    if "theme" not in st.session_state:
        st.session_state["theme"] = "dark"

def inject_theme_js() -> None:
    """每次 rerun 注入冪等 ThemeToggle JS（純 client-side 切換，不觸發 Python rerun）。"""
    import streamlit.components.v1 as components
    components.html(f"<script>{_THEME_JS}</script>", height=0)
```

### `app.py` 呼叫順序

```python
load_css()           # ② 載入 CSS（原有）
init_theme_state()   # ②′ 主題 session_state 初始化（新增，在 CSS 後、actor 解析前）
init_logging()       # ②″ 結構化 log（原有）

actor = resolve_actor()  # ③ 身分解析（原有）
...
render_topbar(actor, cms_base_url=_cms_url, theme=st.session_state["theme"])  # ⑥ 傳入 theme
inject_theme_js()    # ⑦ 注入 JS（新增，在 topbar 渲染後，確保 DOM 元素已存在）
```

> `init_theme_state()` 放在 `actor = resolve_actor()` 之前，是因為 `resolve_actor()` 在某些路徑會呼叫 `st.stop()`，提前初始化確保 session_state 在任何分支都設定完成。

---

## 9. 測試規格

### 9.1 `tests/unit/test_topbar.py` 新增測試（共 9 個）

```python
# ── ThemeToggle：多主題 ──

def test_theme_toggle_dark_shows_moon(actor):
    """theme='dark' 時，ThemeToggle 含月亮 path（MoonPaths SVG）。"""
    html = _build_topbar_html(actor, theme="dark")
    assert "M21 12.79" in html  # moon path d 值

def test_theme_toggle_dark_no_circle(actor):
    """theme='dark' 時，不含太陽 <circle>（圖示互斥）。"""
    html = _build_topbar_html(actor, theme="dark")
    assert "<circle" not in html

def test_theme_toggle_light_shows_sun(actor):
    """theme='light' 時，ThemeToggle 含太陽圖示（circle + 8 line）。"""
    html = _build_topbar_html(actor, theme="light")
    assert "<circle" in html and "<line" in html

def test_theme_toggle_light_no_moon(actor):
    """theme='light' 時，不含月亮 path（圖示互斥）。"""
    html = _build_topbar_html(actor, theme="light")
    assert "M21 12.79" not in html

def test_theme_toggle_aria_pressed_false_when_dark(actor):
    """dark mode：aria-pressed='false'（isLight=False）。"""
    html = _build_topbar_html(actor, theme="dark")
    assert 'aria-pressed="false"' in html

def test_theme_toggle_aria_pressed_true_when_light(actor):
    """light mode：aria-pressed='true'（isLight=True）。"""
    html = _build_topbar_html(actor, theme="light")
    assert 'aria-pressed="true"' in html

def test_theme_toggle_aria_label_switch_to_light_when_dark(actor):
    """dark mode：aria-label='切換為淺色'（下一個動作是切到淺色）。"""
    html = _build_topbar_html(actor, theme="dark")
    assert 'aria-label="切換為淺色"' in html

def test_theme_toggle_aria_label_switch_to_dark_when_light(actor):
    """light mode：aria-label='切換為深色'（下一個動作是切到深色）。"""
    html = _build_topbar_html(actor, theme="light")
    assert 'aria-label="切換為深色"' in html

def test_theme_toggle_default_is_dark(actor):
    """theme 未傳時預設 dark（呼叫端無需明確傳值）。"""
    html = _build_topbar_html(actor)
    assert "M21 12.79" in html
```

### 9.2 `tests/unit/test_theme.py` 新增測試（共 8 個）

```python
from lib.theme import parse_theme, build_theme_cookie_string

# parse_theme
def test_parse_theme_dark():      assert parse_theme("dark") == "dark"
def test_parse_theme_light():     assert parse_theme("light") == "light"
def test_parse_theme_none():      assert parse_theme(None) == "dark"
def test_parse_theme_unknown():   assert parse_theme("system") == "dark"
def test_parse_theme_empty():     assert parse_theme("") == "dark"

# build_theme_cookie_string
def test_cookie_string_contains_theme_value():
    assert "theme=dark" in build_theme_cookie_string("dark")

def test_cookie_string_has_max_age():
    assert "Max-Age=31536000" in build_theme_cookie_string("light")

def test_cookie_string_no_secure_in_dev():
    assert "Secure" not in build_theme_cookie_string("dark", is_prod=False)

def test_cookie_string_has_secure_in_prod():
    assert "Secure" in build_theme_cookie_string("dark", is_prod=True)

def test_cookie_string_has_samesite_lax():
    assert "SameSite=Lax" in build_theme_cookie_string("light")
```

---

## 10. 現有測試影響

| 測試 | 影響 | 處理 |
|---|---|---|
| `test_theme_toggle_has_aria_label` | 測試 `aria-label="切換為深色"` → 此為 light mode 標籤，`theme` 預設改為 `"dark"` 後此測試需更新為 `"切換為淺色"` | **需更新** |
| `test_theme_toggle_has_sun_svg` | 預設 `dark` 後顯示月亮，不再有 `<circle>` | **需更新** |
| `test_theme_toggle_has_class` | 無影響 | 繼續通過 |

> 以上兩個現有測試在 RED 階段確認失敗後一併修正（行為變更，非 bug）。

---

## 11. 不在本規格範圍

- Streamlit 內建元件（按鈕、輸入框、圖表）的主題切換——需改 `config.toml`，目前不支援執行期切換。
- 瀏覽器端 `prefers-color-scheme` 媒體查詢偵測（自動跟隨系統主題）。
- 伺服器端 Python 讀取 cookie（Streamlit 不原生支援；目前以 `st.session_state` 預設值 + JS 修正處理）。
- ThemeToggle 以外的 TopBar 互動（登出按鈕 BFF 流程）。

---

## 12. 相關文件

- [設計系統規格](design-system.md)（Streamlit CSS 原則與 token 來源）
- [TopBar CMS 連結規格](topbar-cms-link.md)（TopBar 整體結構）
- StreamSightFrontend `src/components/ui/ThemeToggle.tsx`（對齊來源）
- StreamSightFrontend `src/lib/theme/ThemeProvider.tsx`（狀態管理與 FOUC guard 來源）
- StreamSightFrontend `src/app/globals.css`（深色 token 來源）
- StreamSightFrontend `src/lib/theme/schema.ts`（Cookie 規格來源）
