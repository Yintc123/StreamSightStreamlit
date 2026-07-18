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

| Token | 值 | 用途 |
|---|---|---|
| primary | `#2563eb` | 主色:主要按鈕、連結、重點 |
| background | `#ffffff` | 頁面底色 |
| secondaryBackground | `#f1f5f9` | 卡片 / 側邊欄 / 區塊底色 |
| text | `#0f172a` | 主要文字 |
| success | `#16a34a` | 正常狀態 / 成功 |
| warning | `#f59e0b` | 一般告警 |
| danger | `#dc2626` | 嚴重告警 / 刪除 |

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

限縮在版面與品牌層級,不逐一 hack 內部元件:

```css
/* 內容區:縮上邊距、限制寬度 */
.block-container { padding-top: 2rem; max-width: 1100px; }

/* 主要按鈕圓角 */
.stButton > button { border-radius: 8px; }

/* 指標卡:加底色與內距,形成卡片感 */
[data-testid="stMetric"] {
    background: #f1f5f9;
    padding: 1rem;
    border-radius: 12px;
}
```

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
