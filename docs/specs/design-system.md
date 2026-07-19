# 設計系統 / 樣式規格(Streamlit)

規範 StreamSight 前端的視覺樣式與 CSS 調整方式。原則:**能用主題(`config.toml`)解決的就不寫 CSS,CSS 只做最小必要微調**,避免 Streamlit 改版導致 class 名稱變動而失效。

## 設計原則

- **單一來源**:顏色、間距、字型集中定義,不在各頁散寫魔術數字。
- **主題優先**:色系與深/淺色一律走 `config.toml`;細部零件才用 CSS。
- **降低耦合**:少依賴 Streamlit 內部 class,狙擊元素改用 `st.container(key=...)` + 屬性選擇器。
- **一次載入**:共用 CSS 集中成一份檔案,於 `app.py` 進入點載入一次。

## 設計 Token

作為 `config.toml` 主題與 `main.css` 變數的唯一依據。

### 顏色

#### 主題色（`config.toml` 直接設定）

| Token | 值 | 用途 |
|---|---|---|
| primary | `#2563eb` | 主色:主要按鈕、連結、重點 |
| background | `#ffffff` | 頁面底色（`surface-page`） |
| secondaryBackground | `#f1f5f9` | 卡片 / 側邊欄底色（`surface-card`） |
| text | `#0f172a` | 主要文字（`ink-AAA`） |
| success | `#16a34a` | 正常狀態 / 成功 |
| warning | `#f59e0b` | 一般告警 |
| danger | `#dc2626` | 嚴重告警 / 刪除 |

#### Sidebar Nav Token（`main.css` 中以字面值寫入）

與 StreamSightFrontend `globals.css` `[data-theme="light"]` 的 CSS 變數**完全對齊**；值取自 Streamlit 側欄實測（stSidebar computed style，2026-07-19）。

| Token 語意 | 對應 Frontend 變數 | 值 | 用途 |
|---|---|---|---|
| `ink-AAA` | `--color-ink-AAA` | `#0f172a` | active 項目文字 |
| `ink-AA` | `--color-ink-AA` | `rgba(15, 23, 42, 0.66)` | 非 active 項目文字 |
| `nav-hover` | `--color-nav-hover` | `rgba(141, 173, 206, 0.15)` | 項目 hover / 按鈕 hover 填色 |
| `nav-active` | `--color-nav-active` | `rgba(141, 173, 206, 0.25)` | 項目 active 填色 |
| `brand` | `--color-brand` | `#2563eb` | 調寬把手 hover 細線色 |

### 間距

以 `rem` 為單位:`xs=0.25` / `sm=0.5` / `md=1` / `lg=1.5` / `xl=2`。

### 字型與圓角

- 字型:`sans serif`(主題設定);等寬用於數值 / 日誌。
- 圓角:一般元件 `8px`,卡片 `12px`。
- 內容最大寬度:`1100px`(寬版頁面可放寬)。

## 主題設定(`config.toml`)

`.streamlit/config.toml`,對應上方顏色 Token:

```toml
[theme]
primaryColor = "#2563eb"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f1f5f9"
textColor = "#0f172a"
font = "sans serif"
```

## CSS 載入方式

外部 CSS 集中於 `styles/main.css`,由進入點載入一次。

```python
# lib/theme.py
import streamlit as st
from pathlib import Path

def load_css(path: str = "styles/main.css") -> None:
    css = Path(path).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
```

```python
# app.py(進入點,在 st.navigation 之前呼叫)
st.set_page_config(page_title="StreamSight", layout="wide",
                   initial_sidebar_state="expanded")
load_css()
```

- 每次 rerun 都會重新注入,無副作用。
- 需在頁面內容渲染前呼叫,避免樣式閃爍。

## 允許的自訂樣式(`styles/main.css`)

限縮在版面與品牌層級,不逐一 hack 內部元件。

### 版面 / 品牌層級

```css
/* 內容區:縮上邊距、限制寬度 */
.block-container { padding-top: 0.5rem; max-width: 1100px; }

/* 元素容器上下 padding 減半（Streamlit 預設 0.5rem → 0.25rem，壓縮垂直空間） */
.stElementContainer { padding-top: 0.25rem; padding-bottom: 0.25rem; }

/* 分隔線（st.divider / <hr>）移除多餘 padding 與 margin */
.stElementContainer:has(hr) { padding-top: 0; padding-bottom: 0; }
.stElementContainer:has(hr) hr { margin: 0; }

/* 主要按鈕圓角 */
.stButton > button { border-radius: 8px; }

/* 指標卡:加底色與內距,形成卡片感 */
[data-testid="stMetric"] {
    background: #f1f5f9;
    padding: 1rem;
    border-radius: 12px;
}
```

### 頂部 Nav Bar（對齊 StreamSightFrontend CmsTopBar）

> **視覺規格來源**：StreamSightFrontend `src/app/cms/CmsTopBar.tsx` + `ThemeToggle.tsx`。  
> 採 `position: fixed; top: 0; left: 0; right: 0`（z-index 999990），覆蓋側欄與主內容頂端。  
> 注入方式：`lib/topbar.py::render_topbar(actor, cms_base_url)` → `st.markdown(html, unsafe_allow_html=True)`。

#### 元件結構

```
CmsTopBar.tsx                       ss-topbar（對應 Streamlit）
├── brand（Stream + Sight accent）   .ss-topbar__brand + .ss-topbar__accent
├── system nav                       .ss-topbar__nav
│   ├── 管理後台（inactive/link）    .ss-topbar__sysitem（<a>）
│   └── 資料平台（active）           .ss-topbar__sysitem.ss-topbar__sysitem--active（<span>）
└── right
    ├── username                     .ss-topbar__username（text-xs text-ink-A）
    ├── ThemeToggle                  .ss-topbar__theme-btn（w-9 h-9 rounded-md + SVG sun）
    └── 登出                        .ss-topbar__sysitem（<button>，與 inactive tab 同樣式）
```

#### Token 對照（light mode）

| Token 語意 | Frontend CSS 變數 | 值 | 元件 |
|---|---|---|---|
| `surface-card` | `--color-surface-card` | `#f1f5f9` | TopBar 底色 |
| `line` | `--color-line` | `rgba(15,23,42,0.12)` | 底部邊框、ThemeToggle hover 填色 |
| `ink-AAA` | `--color-ink-AAA` | `#0f172a` | 品牌文字、ThemeToggle hover 圖示色 |
| `ink-AA` | `--color-ink-AA` | `rgba(15,23,42,0.66)` | inactive tab、ThemeToggle 圖示色 |
| `ink-A` | `--color-ink-A` | `rgba(15,23,42,0.45)` | username 文字 |
| `brand` | `--color-brand` | `#2563eb` | Sight accent、active tab 文字 |
| `brand-overlay` | `--color-brand-overlay` | `rgba(37,99,235,0.12)` | active tab 填色 |
| `nav-hover` | `--color-nav-hover` | `rgba(141,173,206,0.15)` | tab/按鈕 hover 填色 |

#### CSS 規則（`styles/main.css` 節錄）

```css
/* stHeader 壓縮為 height:0 overflow:visible，不可 display:none。
 * 側欄收合後展開按鈕（stExpandSidebarButton）動態注入 stHeader/stToolbar；
 * display:none 會讓 position:fixed 子孫也消失、側欄永遠無法展開。 */
[data-testid="stHeader"] {
    height: 0; min-height: 0; overflow: visible;
    background: transparent; border-bottom: none; padding: 0;
}
[data-testid="stToolbar"] {
    height: 0; min-height: 0; overflow: visible;
    background: transparent; padding: 0;
}

/* 隱藏 stToolbar 內不需要的工具列項目（stExpandSidebarButton 除外）。
 * ⚠ stBaseButton-headerNoPadding 須限定在 stToolbar 內；
 *   stSidebarCollapseButton 也使用同名 testid，不加父選擇器會被一併隱藏。 */
[data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"],
[data-testid="stBaseButton-header"],
[data-testid="stToolbar"] [data-testid="stBaseButton-headerNoPadding"] { display: none; }

/* 側欄展開按鈕（stExpandSidebarButton）：position:fixed 定位於 TopBar 下 8px。
 * z-index 999993 > TopBar 999992 > stSidebar 999991。
 * ⚠ testid = stExpandSidebarButton（非 stSidebarExpandButton）；升版需回歸。 */
[data-testid="stExpandSidebarButton"] {
    position: fixed; top: 56px; left: 8px;   /* 48px TopBar + 8px gap */
    z-index: 999993; width: 28px; height: 28px; border-radius: 8px; background: #f1f5f9;
}
[data-testid="stExpandSidebarButton"] button {
    width: 28px; height: 28px; border-radius: 8px;
    color: rgba(15, 23, 42, 0.66); transition: background-color 150ms ease;
}
[data-testid="stExpandSidebarButton"] button:hover { background-color: rgba(141,173,206,0.15); }

/* TopBar 本體 */
.ss-topbar {
    position: fixed; top: 0; left: 0; right: 0;
    z-index: 999992;        /* > stSidebar(999991) */
    height: 48px; background-color: #f1f5f9;
    border-bottom: 1px solid rgba(15, 23, 42, 0.12);
    display: flex; align-items: center; gap: 8px; padding: 0 16px;
}
.ss-topbar__brand { font-size: 15px; font-weight: 700; color: #0f172a; }
.ss-topbar__accent { color: #2563eb; }
.ss-topbar__sysitem {
    border-radius: 8px; padding: 0 12px; height: 32px;
    font-size: 14px; font-weight: 500; color: rgba(15,23,42,0.66);
}
.ss-topbar__sysitem:hover { background-color: rgba(141,173,206,0.15); }
.ss-topbar__sysitem--active,
.ss-topbar__sysitem--active:hover { background-color: rgba(37,99,235,0.12); color: #2563eb; }
.ss-topbar__username { font-size: 12px; color: rgba(15,23,42,0.45); max-width: 40%; }
/* ThemeToggle：w-9(36px) h-9(36px) rounded-md(6px)；SVG 20×20px(w-5 h-5)
   aria-label="切換為深色"（light mode 太陽圖示；對齊 ThemeToggle.tsx） */
.ss-topbar__theme-btn {
    width: 36px; height: 36px; border-radius: 6px;
    color: rgba(15,23,42,0.66);
    transition: color 150ms ease, background-color 150ms ease;
}
.ss-topbar__theme-btn:hover { color: #0f172a; background-color: rgba(15,23,42,0.12); }

/* 佔位補償：stHeader 壓縮後，側欄與主內容各下移 48px。
 * stSidebarContent 清除預設橫向 padding，由子區塊（stSidebarNav / stSidebarUserContent）自設。 */
[data-testid="stSidebarContent"] { padding-top: 48px; padding-left: 0; padding-right: 0; }
[data-testid="stMain"] { padding-top: 48px; }
```

#### 注意事項

- **資料平台 tab 永遠 active**（Streamlit 即為 資料平台）；**管理後台**連結至 `bff_base_url/cms`（mock 模式下降回 `#`）。
- **username XSS 防護**：`_build_topbar_html` 以 `html.escape()` 處理 `actor.username`。
- **ThemeToggle**：目前只渲染 light mode 太陽圖示（SVG 20px），`aria-label="切換為深色"`；深色切換功能待後續 cycle 接入。
- **登出按鈕**：目前視覺佔位；bff 模式的 CSRF logout 流程待後續 cycle 實作。
- `render_topbar` 使用 `st.markdown(unsafe_allow_html=True)` 而非 `st.html()`，原因是 Streamlit 1.50 的 `AppTest` 尚不支援 `at.html` 屬性驗證，改用 `at.markdown` 可完整覆蓋測試。
- **stHeader / stToolbar 只能用 `height:0`**：不可用 `display:none`，否則注入其中的 `stExpandSidebarButton`（`position:fixed`）也會消失，側欄收合後無法展開。
- **`stBaseButton-headerNoPadding` 必須限定在 stToolbar 下**：Streamlit 對 `stSidebarCollapseButton` 內的按鈕也使用此 testid；無父選擇器限制會一併隱藏收合按鈕。

### 側邊欄 Nav（對齊 StreamSightFrontend CmsSideNav）

> **視覺規格來源**：StreamSightFrontend `src/app/cms/CmsSideNav.tsx`（Spec 016 §4.2–4.3）。  
> Frontend 的 light-mode 顏色值是從 Streamlit stSidebar computed style 實測（2026-07-19）後寫進 `globals.css`，此處反向對齊以達到兩端 Nav 一致。

```css
/* 移除側欄右側邊框（靠 #f1f5f9 vs #ffffff 色差分隔） */
section[data-testid="stSidebar"] { border-right: none; }

/* Nav 容器：對齊 CmsSideNav nav.flex.flex-col.gap-0.5.px-3.py-3
 * gap-0.5 = 2px（項目間距）、px-3 py-3 = 12px 四邊 padding。
 * 改 flex column 以啟用 gap；stSidebarContent 已清除預設橫向 padding（見上方）。 */
[data-testid="stSidebarNav"] {
    display: flex !important; flex-direction: column; gap: 2px; padding: 12px;
}

/* stSidebarNavLinkContainer 是每個 nav item 的外框 div，預設有垂直 padding 造成
 * 28px 連結卻佔 32px 高；歸零後配合 gap: 2px 達成 2px 間距（gap-0.5）。 */
[data-testid="stSidebarNavLinkContainer"] { padding: 0 !important; }

/* Dev Switcher（mock 模式）對齊 12px 橫向 padding（stSidebarContent 已清 0） */
[data-testid="stSidebarUserContent"] { padding-left: 12px; padding-right: 12px; }

/* Nav 連結基底：h-7(28px) rounded-lg(8px) px-2(8px) text-base font-normal */
[data-testid="stSidebarNavLink"] {
    border-radius: 8px; padding: 0 0.5rem; height: 28px;
    display: flex; align-items: center;
    color: rgba(15, 23, 42, 0.66);   /* ink-AA */
    font-weight: 400; text-decoration: none;
    transition: background-color 150ms ease;
}
[data-testid="stSidebarNavLink"]:hover {
    background-color: rgba(141, 173, 206, 0.15); color: rgba(15,23,42,0.66); text-decoration: none;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background-color: rgba(141, 173, 206, 0.25); color: #0f172a; font-weight: 600;
}

/* 收合按鈕（stSidebarCollapseButton）：對齊 CmsSideNav always-visible collapse button。
 * Streamlit 預設 visibility:hidden（僅 hover 顯示）；覆蓋為永遠可見。
 * 按鈕內部使用 stBaseButton-headerNoPadding testid（與 stToolbar 共用）；
 * 注意必須確保 stToolbar 的隱藏規則不影響此處（見 TopBar CSS）。 */
[data-testid="stSidebarCollapseButton"] { visibility: visible !important; }
[data-testid="stSidebarCollapseButton"] button {
    display: inline-flex !important; visibility: visible !important;
    width: 28px; height: 28px; border-radius: 8px;
    color: rgba(15, 23, 42, 0.66); transition: background-color 150ms ease;
}
[data-testid="stSidebarCollapseButton"] button:hover { background-color: rgba(141,173,206,0.15); }

/* 調寬把手：8px 透明，hover 顯示 brand(#2563eb) 1px 細線 */
[data-testid="stSidebarResizeHandle"] { width: 8px; background: transparent; cursor: col-resize; }
[data-testid="stSidebarResizeHandle"]::after {
    content: ''; display: block; width: 1px; height: 100%;
    margin: 0 auto; background: transparent; transition: background-color 150ms ease;
}
[data-testid="stSidebarResizeHandle"]:hover::after { background-color: #2563eb; }
```

**選擇器對應表**

| 元素 | Streamlit selector | CmsSideNav 對應 |
|---|---|---|
| 側欄面板 | `section[data-testid="stSidebar"]` | 外層 `div.bg-surface-card` |
| Nav 容器 | `[data-testid="stSidebarNav"]` | `nav.flex.flex-col.gap-0.5.px-3.py-3` |
| Nav 連結 | `[data-testid="stSidebarNavLink"]` | `<Link className={itemClass(...)}>`|
| 收合按鈕 | `[data-testid="stSidebarCollapseButton"] button` | `button aria-label="收合側欄"` |
| 展開按鈕 | `[data-testid="stExpandSidebarButton"]`（button 本身） | CmsSideNav `absolute left-2 top-2 z-10` |
| 調寬把手 | `[data-testid="stSidebarResizeHandle"]` | `div role="separator"` |

> **展開按鈕位置差異**：Frontend CmsSideNav 的展開按鈕在 sidebar 容器內以 `absolute left-2 top-2` 定位，自然落在 TopBar 下方（因 flex 布局 TopBar 先佔一行）。Streamlit 的展開按鈕（`stExpandSidebarButton`，testid 非 `stSidebarExpandButton`）在 `stToolbar`（`stHeader` 子節點），以 `position:fixed; top:56px; left:8px` 達成等效視覺（TopBar 48px + 8px 間距）。

> **`aria-current="page"` 管理**：`[aria-current="page"]` attribute 由 `st.navigation` 在執行時自動加到當前頁連結上，頁面程式碼無需手動處理。

> ⚠️ `stSidebarCollapseButton`、`stExpandSidebarButton`、`stSidebarResizeHandle`、`stSidebarNav`、`stSidebarNavLinkContainer`、`stSidebarUserContent` 等 `data-testid` 屬於 Streamlit 內部，升版後需回歸驗證（見「風險與注意」）。

## 狙擊特定元素

Streamlit 不保證穩定 class,需精準選取時依序優先:

1. `config.toml` 能設定 → 用主題。
2. 對容器加 `key`:`st.container(key="alert_box")` → Streamlit 會產出對應的
   `.st-key-alert_box`,以此為選擇器最穩定。
3. 需要純 HTML/CSS 片段 → 用 `st.html("<div>…</div>")`。
4. 最後才用 `data-testid`(如 `stMetric`、`stSidebar`),並註明可能隨版本變動。

## 狀態色彩規範

告警與狀態一律套用顏色 Token,跨頁一致:

| 狀態 | 顏色 | 使用頁面 |
|---|---|---|
| 正常 / 成功 | success | 即時監控、資料分析 |
| 一般告警 | warning | 即時監控 |
| 嚴重 / 刪除 | danger | 即時監控、資料管理 |

## 訊息呈現規範

錯誤 / 告警 / 空狀態訊息的**視覺格式**由此規範;**呈現契約**(哪種例外用哪個層級、文案、是否附 `request_id`)的權威在 [錯誤處理規格 §3](error-handling.md#3-呈現契約本規格唯一權威),各頁一律引用,不自訂。

| 層級 | 元件 | 色 Token | 用途 |
|---|---|---|---|
| error | `st.error` | danger | 操作失敗、系統 / 傳輸故障、輸入需修正 |
| warning | `st.warning` | warning | 可恢復 / 暫時性 / 降級中(WS 重連、找不到目標) |
| info | `st.info` | 中性 / secondary | 空狀態、登入前引導 |

- **Icon**:一律用 `st.error` / `st.warning` / `st.info` 內建圖示,不自繪。
- **`request_id`**:僅傳輸層錯誤(`ApiError`)附上,置於訊息**末端**、以**等寬字**呈現,格式「錯誤代碼:`st-a1b2…`」(見 [request-id §4.3](request-id.md))。
- **空狀態**:`st.info` + 一行說明,**取代主內容區**(而非疊加);不揭露技術細節。
- **禁止**:後端原文 / stack trace / SQL / token 出現在 UI 訊息;技術細節只進結構化 log。

## 檔案結構

```
.streamlit/config.toml     # 主題(顏色 / 字型)
styles/main.css            # 共用自訂 CSS
lib/theme.py               # load_css() helper
app.py                     # set_page_config + load_css()
```

## 風險與注意

- Streamlit 升版可能改動 `data-testid` / 內部 class,依賴它的規則需回歸測試。
- `unsafe_allow_html=True` 僅用於載入自家 CSS,不得注入未信任內容。
- 大幅客製(超出 CSS 可及)才考慮 Streamlit Components(React),另立規格。

## 相關文件

- [錯誤處理](error-handling.md)(訊息呈現契約:層級 / 文案 / request_id)
- [應用骨架 / 基礎架構](app-skeleton.md)
- [前端頁面結構](frontend-pages.md)
- [技術架構](../architecture.md)
