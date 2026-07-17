# 頁面規格:登入 / 註冊

- 頁面編號:1
- 對應模組:模組 1 認證
- 存取權限:未登入使用者
- 導覽:未登入時為唯一註冊的頁面

## 目的

提供使用者登入與註冊入口,並在成功後建立 session 與角色,決定後續可存取的頁面。

## 版面

以 `st.tabs` 分為兩個分頁:

| 分頁 | 內容 |
|---|---|
| 登入 | 帳號、密碼、登入按鈕 |
| 註冊 | 帳號、密碼、確認密碼、Email、註冊按鈕 |

## UI 版面規劃

窄欄置中卡片(未登入者唯一頁面,聚焦表單)。以 `st.columns([1, 1.4, 1])` 置中,中欄放標題與 `st.tabs`。

```
                 ┌──────────── 置中欄 ────────────┐
                 │           StreamSight          │  ← st.title / logo
                 │        資料監控與分析平台        │  ← st.caption
                 │  ┌──────────────────────────┐  │
                 │  │  [ 登入 ]   [ 註冊 ]      │  │  ← st.tabs
                 │  ├──────────────────────────┤  │
                 │  │  帳號  [________________] │  │  ← st.text_input
                 │  │  密碼  [________________] │  │  ← type="password"
                 │  │        [     登入     ]   │  │  ← st.form_submit_button
                 │  │  ⚠ 帳號或密碼錯誤          │  │  ← st.error(inline)
                 │  └──────────────────────────┘  │
                 └────────────────────────────────┘
```

| 區域 | 元件 | 備註 |
|---|---|---|
| 置中容器 | `st.columns([1, 1.4, 1])` | 只用中欄,左右留白 |
| 分頁 | `st.tabs(["登入", "註冊"])` | 兩表單各自獨立 |
| 登入表單 | `st.form("login")` + 2×`text_input` + `form_submit_button` | 密碼 `type="password"` |
| 註冊表單 | `st.form("register")` + 帳號/密碼/確認密碼/Email + 送出 | 送出後提示改至登入分頁 |
| 錯誤 | `st.error`(表單下方 inline) | 登入失敗不透露帳號或密碼 |

- 送出用 `st.form` 包住,避免逐欄 rerun;成功後 `st.session_state` 寫入並 `st.switch_page` 導向儀表板。

## 功能細節

### 登入
- 欄位:帳號(text)、密碼(password)。
- 驗證:呼叫後端認證 API(Argon2 比對),前端不查 DB、不雜湊。
- 成功:後端回傳 JWT → 寫入 `session_state`(`token`、`username`、`role`),導向儀表板。
- 失敗:顯示「帳號或密碼錯誤」,不透露是帳號或密碼哪個錯。

### 註冊
- 欄位:帳號、密碼、確認密碼、Email。
- 驗證:帳號唯一、兩次密碼一致、密碼強度、Email 格式。
- 成功:建立使用者(預設角色 `user`),提示改至登入分頁。
- 失敗:對應欄位顯示錯誤。

## 資料

- users 表由**後端**擁有:`id, username(唯一), password_hash, email, role, created_at`;前端僅透過認證 API 存取,不直接連 DB。
- 角色:`user` / `admin`。

## 狀態與錯誤處理

- 已登入者進入本頁 → 直接導向儀表板。
- 帳號重複、密碼不一致、格式錯誤 → inline 錯誤訊息。

## 依賴 / 備註

- 認證走 **FastAPI 認證 API**(見 [ADR 0002](../../decisions/0002-streamlit-as-api-client.md)):登入 / 註冊呼叫後端端點,取得 JWT 存於 `st.session_state`。
- 前端**不使用 `streamlit-authenticator`、不自行雜湊密碼**;密碼雜湊(Argon2)由後端負責。
