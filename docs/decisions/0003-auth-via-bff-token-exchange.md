# ADR 0003:Streamlit 認證採「BFF Session 換短命 JWT」(Design B)

- 狀態:已採用
- 日期:2026-07-18
- 關聯:[ADR 0002](0002-streamlit-as-api-client.md)(Streamlit 為純 API Client)、[認證流程規格](../specs/auth-flow.md)、[頁面規格:登入 / 註冊](../specs/pages/01-login.md)
- 外部參考:`StreamSightFrontend`(Next.js BFF)`docs/specs/001-bff-infrastructure.md` 及子 spec `001b`(session-store)/`001c`(session-service)/`001d`(csrf);`StreamSightBackend`(FastAPI,JWT Bearer)

> ## 🔒 首要設計目標:瀏覽器永遠拿不到 JWT
>
> 這是本 ADR 與整套認證架構的**第一因**——底下每個決策(Streamlit 為純 API Client、唯一 BFF、換 token 而非讀 Redis、JWT 只存 server 記憶體)都是為了守住這一條而推導出來的。**讀本 ADR 時,請以「是否讓 JWT 暴露到瀏覽器」作為衡量每個方案的首要標準。**
>
> JWT(FastAPI 的 Bearer access token)**全程不進瀏覽器**:它只在 **Streamlit Python server 記憶體**(`session_state`,不落檔 / log / 渲染);使用者端只有一顆加密共享 cookie 與渲染後 UI。這也是下方 Design A/B/C 取捨的共同量尺——B 讓 JWT 進 Streamlit **server**(不進瀏覽器)、A 連 server 都不進、C 則連信任根都外流。

## 背景

StreamSight 有多個前端共用同一批使用者:**主前端**(`StreamSightFrontend`,Next.js)與本專案 **Streamlit 儀表板**。目標是讓使用者**在主前端登入後,進 Streamlit 免再次登入**(簡易 SSO)。

考察主前端後,確認其認證是一套成熟的 **BFF 架構**:

- 瀏覽器持有一顆 **iron-session 加密封裝**的 cookie(`streamsight_session`),內容僅 `{ sessionId }`,以 `SESSION_SECRET` 加密簽章。
- 真正的 session(含後端 JWT access/refresh token、user、role、csrfToken)存在 **BFF 的 Redis**。
- **JWT 只存在於 Redis + BFF↔FastAPI 之間,不進瀏覽器**。
- CSRF 用 Synchronizer Token(`X-CSRF-Token`)+ Origin 白名單;access token 3h、refresh 30d,由 BFF 以 Redis 分散式鎖去重 refresh。

要讓 Streamlit 參與這套 SSO,必須先面對 **Streamlit 的三個結構性限制**(下節詳述),它們決定了可行方案的形狀:

1. **Streamlit 無法 `Set-Cookie`**(見 §「關鍵限制詳解」)。
2. Streamlit 的 API 呼叫由**伺服器端**發出,**不會自動夾帶瀏覽器 cookie**。
3. 那顆 cookie 是**加密**的,Streamlit **無法自行解出 `sessionId`**。

---

## 關鍵限制詳解:為什麼 Streamlit 沒辦法透過 response 物件 `Set-Cookie`

> 這一段是本 ADR 的技術核心,說明「登入 / 登出為何必須委派主前端」的根因。

### 一般 Web 框架:你手上有 response,所以能寫 `Set-Cookie`

在 Flask / FastAPI / Express 這類框架,一個請求對應一個 **handler**,handler **收到 `request`、回傳(或持有)一個 `response`**。設定 cookie 的本質是**在 HTTP 回應寫一個 `Set-Cookie` 標頭**,而你既然握有 response,就能寫:

```python
# FastAPI:handler 回傳/持有 response,可直接 set_cookie
response.set_cookie("session", value, httponly=True, secure=True)
```

**能不能種 cookie,取決於「你有沒有一個能寫標頭的 response 物件」。**

### Streamlit:response 物件被 Tornado 內部包走了,你的 script 碰不到

Streamlit 的伺服器是建在 **Tornado**(Python async web server)之上,但它的**執行模型和一般框架完全不同**:

1. **你的 `app.py` 不是一個 request handler。** 它沒有 `(request) -> response` 的簽章,也沒有回傳值被當成 HTTP 回應。
2. 瀏覽器首次載入時,Tornado 送出的是 Streamlit 的**靜態外殼**(HTML/JS);**那個 HTTP 回應由 Streamlit 內部的 Tornado handler 產生,不經過你的程式**。
3. 之後應用改走 **WebSocket**。你的 script 由 Streamlit 的 **ScriptRunner** 於每次互動**從頭重跑(rerun)**,`st.*` 呼叫產生的是一連串 **delta 訊息(ForwardMsg)**,透過 WebSocket **推送**給瀏覽器更新畫面。
4. 真正的 HTTP 回應與 WebSocket 訊框,**由 Streamlit 內部的 Tornado handler(`tornado.web.RequestHandler` 及對應的 response)建立與管理**。這些 response 物件**活在 Streamlit 伺服器內部,從不暴露給你的 script**。

因此:

> **你的程式碼裡根本沒有一個 response 物件可以掛 `Set-Cookie`。** 唯一「擁有 response、能寫回應標頭」的是 Streamlit / Tornado 自己,而它**沒有開放這個介面**給應用層。

### 連讀 cookie 都是唯讀,更沒有「寫」的對應 API

Streamlit 提供 `st.context.cookies`,但它是**唯讀**的——它把**瀏覽器送上來**的 Cookie 標頭解析出來給你讀,**沒有 `st.context.set_cookie` 這種對應物**,也沒有任何官方 API 能讓 script 送出 `Set-Cookie`。

```python
raw = st.context.cookies.get("streamsight_session")  # 讀得到(瀏覽器送來的)
# 但「寫」cookie —— 沒有這種 API。
```

> `HttpOnly` 只擋瀏覽器端 JS,不擋伺服器;所以 `st.context.cookies` **讀得到** httpOnly cookie(仍待 spike 驗證,見 auth-flow.md §2.3)。但「讀得到」和「能不能寫」是兩回事——**讀是唯讀 API,寫則完全沒有 API。**

### 唯一的「繞道」不算數

Custom component 可以在 iframe 內用 JS 操作 `document.cookie`。但那是**瀏覽器端 JS 寫的 cookie**,**無法設 `HttpOnly`**(JS 設不出 httpOnly),與「伺服器端 `Set-Cookie` 一顆 httpOnly、Secure 的 session cookie」不是同一回事,不能拿來當安全 session 用。所以這條路對本案**無效**。

### 直接後果

種 session cookie(登入)與清 session cookie(登出)**本質上都需要寫 HTTP 回應標頭**,而 Streamlit **沒有能寫回應的 response 物件**。因此:

- **Streamlit 不能自己擁有登入**(登入要 `Set-Cookie`)→ 登入必須**委派給能寫回應的元件**(主前端 BFF)。
- **Streamlit 不能自己清 cookie 登出** → 登出必須**呼叫 BFF**,由 BFF `Set-Cookie: Max-Age=0` 清除。

### 重要界線:這個限制只逼出「委派登入/登出」,不是本次資安風險的成因

必須釐清因果,避免誤解:

- 「不能 `Set-Cookie`」是一個**功能限制**,它逼出的結論是「**登入 / 登出委派主前端**」。
- 它**不是**「Streamlit 持有主金鑰、被攻破可偽造身分」那個**資安風險**的成因。那個風險來自另一個**選擇**——是否把 `SESSION_SECRET` + Redis 交給 Streamlit 自行解密 cookie(即被否決的 Design C,見下)。
- 佐證:Design B 與 Design C **都有**這個「不能 Set-Cookie」限制,但 B 幾乎無此資安風險、C 才有。同樣的限制、不同的風險 ⇒ 風險不源自此限制。

---

## 決策

採用 **Design B:Streamlit 用加密 cookie 向 BFF 換取「身分 + 短命 JWT」,再拿 JWT 直連 FastAPI。**

```
Streamlit
  │ ① st.context.cookies 讀到加密 cookie
  │ ② 原封轉發:GET /api/auth/session  (Cookie: streamsight_session=<sealed>)
  ▼
Next.js BFF ── 解封 cookie → sessionId → 查 Redis →(access token 將過期則先 refresh)
  │ ③ 回 { user, role, accessToken, expiresAt }   或 401
  ▼
Streamlit
  │ ④ 用 accessToken 當 Bearer
  ▼
FastAPI(直連,處理所有業務 / 資料 / WebSocket 即時監控)
```

- **難的事(解封、查 Redis、refresh 鎖)全部留在 BFF**,單一來源、已測試。
- **Streamlit 只做**:讀 cookie → 轉發換 token → 帶 Bearer 打 FastAPI。它**不持有** `SESSION_SECRET`、**不連** Redis,手上只有**一顆短命、可撤銷的 access token**。
- **資料平面維持 Streamlit → FastAPI 直連**(符合 [ADR 0002]);只有「換 token / 登出」少數認證呼叫回 BFF,且 introspection 結果以短 TTL 快取。
- **登入 / 登出委派主前端**(見上節限制)。

---

## 考量過但否決的方案

### Design A:Streamlit 當純 BFF 消費者(所有請求都經 BFF proxy)

- 做法:Streamlit **所有**請求(含資料)都轉發給 Next.js BFF,由 BFF 注入 JWT、處理 refresh;**JWT 完全不進 Streamlit**(安全性最高)。
- 否決理由:**前端必須把 Streamlit 需要的每一個資料端點都 proxy 出來**,前端範圍大幅擴張;且**違反 [ADR 0002]**(Streamlit 不再直連 FastAPI)。
- 保留條件:若日後出現「JWT 絕不得進入 Streamlit」的硬性法遵 / 資安要求,可回頭改採 A(需修 ADR 0002)。

### Design C:Streamlit 共用 Redis + `SESSION_SECRET`,自行解封 cookie

- 做法:Streamlit 與 BFF 共用同一顆 Redis,並透過 SSM 共用 `SESSION_SECRET`,在 Python 端**自行解封 iron-session cookie** → 取 sessionId → 直接讀 Redis 的 session。
- 否決理由:
  1. **信任邊界擴大(最關鍵)**:`SESSION_SECRET` + Redis 存取進入 Streamlit → **Streamlit server 一旦被攻破,即可偽造任意使用者(含 admin)的 session,連主前端一起淪陷**。Streamlit 的攻擊面(檔案上傳 / CSV/Excel 解析 / 反序列化 / 龐大原生相依樹)天生比「驗證後轉發」的 BFF 廣得多,不適合保管信任根。
  2. **跨語言複製 security-critical 邏輯**:得在 Python 重刻 iron-session 解封與 refresh 鎖協定,並與 JS 版**永久同步**;版本漂移會無聲壞掉或造成安全落差。
  3. **schema / 金鑰輪換耦合**:耦合 BFF 的 `StoredSession` 內部 schema;secret 輪換要跨 2 服務 2 語言協調,協調失誤 → 集體登出。
  4. **違反 [ADR 0002]**(Streamlit 直接持有資料層連線)。
- 關於 SSM:用 SSM 共用 secret 只解決了「機密的安全分發與輪換」,**解決不了**上述 1~4——尤其**「secret 送達 Streamlit 之後常駐於其記憶體、而該 server 被攻破」這個風險本體**。「沒有 cookie 就導回登入」也擋不住此風險,因為攻擊者拿到 secret 後可**自行偽造合法 cookie**,根本不會落入「缺 cookie」的分支。

### 天真方案:直接讀明文 sessionId 打 FastAPI `/auth/me`(原草稿假設)

- 否決理由:**技術上不成立**。cookie 是加密的(讀到也解不出 sessionId);且 FastAPI `/auth/me` 只吃 **Bearer JWT**、不吃 cookie,Streamlit 手上沒有 JWT。

---

## 理由

- **資安(首要)**:守住「**瀏覽器拿不到 JWT**」這條首要設計目標——JWT 只進 Streamlit server 記憶體、不進使用者端;`SESSION_SECRET` 與 Redis 留在 BFF;Streamlit 被攻破時,損害被框在**單一使用者、短命且可撤銷的 token**,而非整個系統的信任根。
- **一致性**:資料平面維持 Streamlit → FastAPI 直連,延續 [ADR 0002]。
- **前端改動最小**:只需新增一個 introspection 端點(+ logout),重用 BFF 既有、已測試的解封 / Redis / refresh 邏輯,**不在 Python 重刻 crypto 與併發**。
- **契約耦合而非實作耦合**:B 只耦合一個 HTTP 端點的回應形狀(鬆);C 耦合 crypto 格式 + schema + secret(緊)。

---

## 影響

### 主前端(需配合)
- 新增 **`GET /api/auth/session`**:解封 cookie → 查 Redis →(必要時 refresh)→ 回 `{ user, role, accessToken, expiresAt }` 或 401(GET,CSRF 豁免)。
- 新增 **`POST /api/auth/logout`**:失效 Redis session + `Set-Cookie: Max-Age=0`(同 `Domain`)。
- 新增 **`SESSION_COOKIE_DOMAIN=.<父網域>`** 並套進 iron-session `cookieOptions.domain`(目前 host-only,Streamlit 收不到 cookie)。
- 把 Streamlit 的來源網域加入 **`ALLOWED_ORIGINS`**(logout 等 unsafe method 的 Origin 檢查)。

### 本專案(Streamlit)
- 新增 `lib/api_client.py`(introspection + FastAPI 呼叫 + 401→重換 token 重試)、`lib/auth.py`(純邏輯:解析 introspection、role 映射、是否需 refresh)、`lib/state.py`、導向 helper。
- **登入頁改為導向 / 載入頁**:[01-login.md](../specs/pages/01-login.md) 需修訂——Streamlit 不再自建登入 / 註冊表單,改導向主前端。
- **`st.cache_data` 是全域跨使用者快取**:凡與身分 / 使用者資料有關的快取,**key 必含 cookie 值**,避免跨使用者洩漏。
- **授權以後端為準**:頁面依 role 動態註冊只是 UX;真正授權由 **FastAPI 每次呼叫驗 JWT** 強制(defense in depth)。

### 硬性前提(部署前必須確認)
- **同父網域**(主前端與 Streamlit);不同註冊網域則本方案不成立,需改 OAuth/SSO redirect。
- **spike**:實測 `st.context.cookies` 能否讀到 httpOnly cookie。

### 對既有 ADR
- [ADR 0002] 的「登入 / 註冊呼叫後端 auth 端點取得 JWT,存於 `session_state`」細節,**修正**為「登入委派主前端 BFF;Streamlit 經 `GET /api/auth/session` introspection 取得短命 JWT」。資料存取「一律經 API、不連 DB」的原則**不變**。

---

## 參考

- [ADR 0002:Streamlit 一律透過 FastAPI 存取資料](0002-streamlit-as-api-client.md)
- [認證流程規格 auth-flow.md](../specs/auth-flow.md)(完整流程、風險盤點、TDD 測試計畫)
- 主前端 BFF spec:`StreamSightFrontend/docs/specs/001b-session-store.md`(iron-session + Redis)、`001c-session-service.md`(refresh 鎖)、`001d-security-csrf.md`
