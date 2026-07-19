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
| 預設主題 | `dark` | `light`（暫時固定） |
| 圖示邏輯 | `isLight` → 太陽；`!isLight` → 月亮 | 同（SVG 已實作，按 `theme` 參數選圖） |
| 按鈕狀態 | 可點擊 | `disabled`（功能待啟用） |
| `aria-pressed` | `isLight`（`"true"/"false"`） | 未使用（按鈕 disabled） |
| `aria-label` | `isLight ? '切換為深色' : '切換為淺色'` | 靜態 `"切換為深色"` |
| Cookie 名稱 | `theme` | `theme` |
| Cookie Max-Age | 31,536,000 秒（1 年） | 同 |
| Cookie SameSite | `Lax` | 同 |
| 未知值收斂 | `dark` | `light` |
| FOUC guard | `data-theme-ready` mount 後掛上 | 同（JS 注入後掛） |
| 過渡動畫 | 150ms ease（color / bg / border） | 同 |
| `prefers-reduced-motion` | `transition: none !important` | 同 |
| dark token 來源 | `globals.css` `@theme` | `main.css` `html[data-theme="dark"]` |
| light token 來源 | `globals.css` `html[data-theme="light"]` | `main.css`（現有字面值） |

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

---

## 6. JS 注入（`inject_theme_js()`）

`lib/theme.py` 的 `_THEME_JS`，於 `app.py` 每次 rerun 均呼叫。

目前實作：固定設 `data-theme="light"` 並掛上 FOUC guard，無 click handler。

```javascript
(function () {
  var pdoc = window.parent.document;
  pdoc.documentElement.dataset.theme = 'light';
  pdoc.documentElement.setAttribute('data-theme-ready', '');
})();
```

#### 未來（啟用切換功能時）需恢復的邏輯

| 操作 | 說明 |
|---|---|
| `readCookie()` | 讀 `theme` cookie，未知值收斂到 `'light'` |
| `applyTheme(t)` | 設 `data-theme`，寫 cookie（冪等） |
| `syncButton(t)` | 換 SVG、更新 `aria-pressed` / `aria-label` |
| click 監聽器 | `parent.__ssThemeReady` 旗標防止重複註冊 |

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

- Streamlit 內建元件（按鈕、輸入框、圖表）的主題切換——需改 `config.toml`，目前不支援執行期切換。
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
