# 頁面規格:未登入導向頁(Auth Gate)

- 頁面編號:1
- 對應模組:模組 1 認證
- 存取權限:未登入使用者
- 導覽:未登入時為唯一註冊的頁面
- 關聯:[ADR 0003](../../decisions/0003-auth-via-bff-token-exchange.md)、[認證流程規格](../auth-flow.md)

> **本頁已改版**(見 [ADR 0003](../../decisions/0003-auth-via-bff-token-exchange.md)):採 Design B「BFF session 換短命 JWT」後,**Streamlit 不再自建登入 / 註冊表單**。因為 Streamlit 無法 `Set-Cookie`(無 response 物件),登入 / 註冊**一律委派主前端**;本頁退化為「**未登入時的導向 / 載入頁**」,唯一職責是把使用者送去主前端登入頁。

## 目的

在使用者**未持有有效 session** 時顯示,並將其**導向主前端登入頁**;登入成功後由主前端種下共享 cookie 並導回 Streamlit。本頁**不收帳密、不呼叫登入 API、不建立 session**。

## 觸發時機

由 `app.py` 的 auth gate 決定(見 [auth-flow.md §4](../auth-flow.md)):

1. 讀 `st.context.cookies` 取加密 cookie。
2. 轉發 BFF `GET /api/auth/session`。
   - **200** → 寫入身分 / role,依角色動態註冊業務頁,導向儀表板;**不顯示本頁**。
   - **401 / 無 cookie** → 只註冊本頁並顯示,啟動導向。

## 版面

窄欄置中、極簡載入卡片(未登入者唯一頁面,聚焦「正在前往登入」)。以 `st.columns([1, 1.4, 1])` 置中。

```
                 ┌──────────── 置中欄 ────────────┐
                 │           StreamSight          │  ← st.title / logo
                 │        資料監控與分析平台        │  ← st.caption
                 │  ┌──────────────────────────┐  │
                 │  │      ⟳ 正在前往登入…       │  │  ← st.spinner / 文字
                 │  │                          │  │
                 │  │   若未自動跳轉,請點此:    │  │
                 │  │        [ 前往登入 ]        │  │  ← 手動 fallback 連結
                 │  └──────────────────────────┘  │
                 └────────────────────────────────┘
```

| 區域 | 元件 | 備註 |
|---|---|---|
| 置中容器 | `st.columns([1, 1.4, 1])` | 只用中欄,左右留白 |
| 標題 | `st.title` / logo + `st.caption` | 品牌一致 |
| 導向提示 | 文字 + `st.spinner` | 「正在前往登入…」 |
| 自動導向 | `st.components.v1.html`(注入 `window.top.location.href = <登入 URL>`) | 進頁即觸發 |
| 手動 fallback | `st.link_button("前往登入", <登入 URL>)` | 自動導向被 CSP / iframe 擋住時的後備 |

## 功能細節

### 導向登入
- 目標 URL:主前端登入頁 + **回跳參數**,例:
  `https://app.example.com/login?next=https://dash.example.com/<原路徑>`
- 導向方式:注入 JS `window.top.location.href = ...`(需導**整個頁面**,非 iframe 內層);同時提供 `st.link_button` 手動後備。
- `next` 由 Streamlit 產生**自身**的回跳網址;**主前端端**必須對 `next` 做**白名單驗證**(僅允許 Streamlit 網域),避免 open-redirect。

### 導向註冊
- 同理提供「註冊」連結,導向主前端註冊頁(`https://app.example.com/register?next=...`)。
- Streamlit **不提供**註冊表單、不呼叫 `/auth/register`。

### 登入成功後
- 主前端種下共享 cookie(`Domain=.<父網域>`)後,依 `next` 導回 Streamlit。
- Streamlit 重跑 → auth gate 讀到 cookie → introspection 200 → 進入儀表板(**不再顯示本頁**)。

## 狀態與錯誤處理

- **已登入者**進入本頁(理論上不會發生,gate 已擋)→ 直接導向儀表板。
- **introspection 逾時 / BFF 不可用**:顯示「暫時無法連線,請稍後重試」+ 手動「前往登入」後備;不進入業務頁。
- **導向被瀏覽器擋下**(CSP / 第三方情境):依賴手動 `st.link_button` 後備。

## 資料

- 本頁**不存取任何 users 資料**、不碰 DB、不呼叫認證憑證端點。
- 身分 / 角色由 auth gate 經 BFF introspection 取得(見 [auth-flow.md](../auth-flow.md)),非本頁職責。

## 依賴 / 備註

- 認證流程與端點契約見 [auth-flow.md](../auth-flow.md);決策背景見 [ADR 0003](../../decisions/0003-auth-via-bff-token-exchange.md)。
- 需設定:主前端**登入頁 URL**、**註冊頁 URL**(放 `lib/config.py`)。
- 登入 / 註冊 / 密碼雜湊(Argon2)全由**主前端 BFF + 後端**負責;Streamlit 端無憑證處理邏輯。
- **硬前提**:主前端與 Streamlit 同父網域(否則 cookie 不共享,見 [auth-flow.md §2](../auth-flow.md))。
