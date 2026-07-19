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

### 側邊欄 Nav（對齊 StreamSightFrontend CmsSideNav）

> **視覺規格來源**：StreamSightFrontend `src/app/cms/CmsSideNav.tsx`（Spec 016 §4.2–4.3）。  
> Frontend 的 light-mode 顏色值是從 Streamlit stSidebar computed style 實測（2026-07-19）後寫進 `globals.css`，此處反向對齊以達到兩端 Nav 一致。

```css
/* 移除側欄右側邊框（靠 #f1f5f9 vs #ffffff 色差分隔） */
section[data-testid="stSidebar"] { border-right: none; }

/* Nav 連結基底：h-7(28px) rounded-lg(8px) px-2 text-base font-normal */
[data-testid="stSidebarNavLink"] {
    border-radius: 8px;
    padding: 0 0.5rem;
    height: 28px;
    display: flex;
    align-items: center;
    color: rgba(15, 23, 42, 0.66);   /* ink-AA */
    font-weight: 400;
    text-decoration: none;
    transition: background-color 150ms ease;
}

/* hover：bg-nav-hover = rgba(141,173,206,0.15) */
[data-testid="stSidebarNavLink"]:hover {
    background-color: rgba(141, 173, 206, 0.15);
    color: rgba(15, 23, 42, 0.66);
    text-decoration: none;
}

/* active：bg-nav-active = rgba(141,173,206,0.25)、ink-AAA、font-semibold */
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background-color: rgba(141, 173, 206, 0.25);
    color: #0f172a;   /* ink-AAA */
    font-weight: 600;
}

/* 收合 / 展開按鈕：28×28px rounded-lg hover:bg-nav-hover */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarExpandButton"] button {
    width: 28px; height: 28px; border-radius: 8px;
    transition: background-color 150ms ease;
}
[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="stSidebarExpandButton"] button:hover {
    background-color: rgba(141, 173, 206, 0.15);
}

/* 調寬把手：8px 透明，hover 顯示 brand(#2563eb) 1px 細線 */
[data-testid="stSidebarResizeHandle"] { width: 8px; background: transparent; cursor: col-resize; }
[data-testid="stSidebarResizeHandle"]::after {
    content: ''; display: block; width: 1px; height: 100%;
    margin: 0 auto; background: transparent;
    transition: background-color 150ms ease;
}
[data-testid="stSidebarResizeHandle"]:hover::after { background-color: #2563eb; }
```

**選擇器對應表**

| 元素 | Streamlit selector | CmsSideNav 對應 |
|---|---|---|
| 側欄面板 | `section[data-testid="stSidebar"]` | 外層 `div.bg-surface-card` |
| Nav 連結 | `[data-testid="stSidebarNavLink"]` | `<Link className={itemClass(...)}>`|
| 收合按鈕 | `[data-testid="stSidebarCollapseButton"] button` | `button aria-label="收合側欄"` |
| 展開按鈕 | `[data-testid="stSidebarExpandButton"] button` | `button aria-label="展開側欄"` |
| 調寬把手 | `[data-testid="stSidebarResizeHandle"]` | `div role="separator"` |

> **`aria-current="page"` の管理**：`[aria-current="page"]` attribute 由 `st.navigation` 在執行時自動加到當前頁連結上，頁面程式碼無需手動處理。

> ⚠️ `stSidebarCollapseButton`、`stSidebarExpandButton`、`stSidebarResizeHandle` 等 `data-testid` 屬於 Streamlit 內部，升版後需回歸驗證（見「風險與注意」）。

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
