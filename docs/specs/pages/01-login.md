# Auth Gate 導向規格(未登入跳轉)

- 對應模組:模組 1 認證
- 實作位置:`app.py`(非獨立頁面檔)
- 存取觸發:未登入使用者(僅 `AUTH_MODE=bff`)
- 關聯:[ADR 0003](../../decisions/0003-auth-via-bff-token-exchange.md)、[認證流程規格](../auth-flow.md)

> **本規格已從「登入頁」改版為「Auth Gate 導向」**:採 Design B 後 Streamlit 無法 `Set-Cookie`,登入一律委派 Next.js 主前端。`pages/gate.py` 已刪除；未登入邏輯集中在 `app.py` 並以 `<meta http-equiv="refresh">` 跳轉。

## 目的

使用者**未持有有效 session** 時,`app.py` 立即把瀏覽器整頁導向 Next.js 登入頁;登入成功後由主前端種下共享 cookie 並導回 Streamlit。Streamlit 端**不收帳密、不呼叫登入 API、不建立 session**。

## 觸發時機

`app.py` 每次 rerun 執行如下:

1. 呼叫 `resolve_actor()`。
2. **`actor is None`**(無 cookie 或 introspection 401)→ 以下邏輯跳轉並 `st.stop()`。
   - `mock` 模式 `resolve_actor()` 恆回 `Actor`,**不會觸發此分支**。

## 實作(`app.py` 核心邏輯)

```python
if actor is None:   # 僅 AUTH_MODE=bff 會發生
    _s = get_settings()
    _login_url = f"{_s.bff_base_url}{_s.bff_login_path}"
    st.markdown(
        f'<meta http-equiv="refresh" content="0; url={_login_url}">',
        unsafe_allow_html=True,
    )
    st.stop()
```

- **跳轉目標**:`BFF_BASE_URL + BFF_LOGIN_PATH`(預設 `http://localhost:3000/login`)。
- **設定**:`BFF_LOGIN_PATH`(預設 `/login`,可覆寫)→ 見 [config §3.3](../config.md)。
- **備援**:瀏覽器若不支援 meta refresh,無法自動跳轉;可視需求加 `st.link_button` 手動後備。

## 登入成功後

主前端種下共享 cookie(`Domain=.<父網域>`)後導回 Streamlit。Streamlit 重跑 → `resolve_actor()` 讀到 cookie → introspection 200 → 進入業務頁。

## 設定項

| 設定 | env 變數 | 預設 | 說明 |
|---|---|---|---|
| BFF base URL | `BFF_BASE_URL` | `http://localhost:3000` | Next.js 主前端 |
| 登入路徑 | `BFF_LOGIN_PATH` | `/login` | Next.js 登入頁路徑 |

## 依賴 / 備註

- 認證流程與端點契約見 [auth-flow.md](../auth-flow.md);決策背景見 [ADR 0003](../../decisions/0003-auth-via-bff-token-exchange.md)。
- **硬前提**:主前端與 Streamlit 同父網域(否則 cookie 不共享)。
- 登入 / 註冊 / 密碼雜湊(Argon2)全由主前端 BFF + 後端負責;Streamlit 端無憑證處理邏輯。
