# 規格:Auth 模組(`lib/auth.py` 契約)

`lib/auth.py` 是 Streamlit 的**身分單一出口**:對 `app.py` 提供 `resolve_actor()`,對 `api_client` 提供 token / cookie 接縫。本規格定義其**可實作契約**,涵蓋 **mock** 與 **bff** 兩模式。

- 協定層(bff SSO / Design B 流程、端點契約)委派 [認證流程規格](auth-flow.md),本檔**不重寫**。
- 型別 `Actor` 沿用 [資料來源 §資料契約](data-source.md#資料契約型別定義);上層流程見 [應用骨架 §3–§4](app-skeleton.md#3-進入點-apppy-職責與順序)。
- 前提旗標:`AUTH_MODE=mock|bff`(骨架 §2)。

---

## 1. 統一型別:`Actor`(廢除 `Identity`)

**全專案身分型別一律為 `Actor`**(`models.Actor`),不再使用 `Identity`——兩者為同一概念,本規格起以 `Actor` 為唯一名稱,`auth-flow.md` 的 `Identity` 同義改稱 `Actor`。

```python
# models.Actor(見 data-source 規格)
@dataclass
class Actor:
    username: str
    role: Literal["user", "admin"]
    grade: Optional[int] = None      # admin → AdminRole 數值 0/50/100/999;存取軸
```

- `resolve_actor()` 回傳 `Optional[Actor]`;下游(頁面、`can_edit`/`can_write`、`build_pages`)只認 `Actor`。
- **本系統為 admin-only**:`role` 恆 `"admin"`,存取差異由 `grade` 決定(見[前端頁面結構 §存取控制](frontend-pages.md#存取控制本節為存取軸的單一真相));故 `resolve_actor` 必須把 introspection 回應的 `grade` 一併帶入 `Actor`,否則 `can_write` 判不到 viewer（grade=0）。

---

## 2. 對外介面

| 函式 | 簽章 | 模式 | 職責 |
|---|---|---|---|
| 身分出口 | `resolve_actor() -> Optional[Actor]` | 全部 | `app.py` 唯一入口;吸收 mock/bff 差異(§3) |
| 頁面守衛 | `require_auth() -> None` | 全部 | 頁面先頭兜底;bff 模式下 `session_state["actor"]` 未設則 meta refresh 跳轉登入頁並 `st.stop()`(詳見§3a) |
| role 映射 | `map_role(raw) -> Literal["user","admin"]` | bff | 後端數值 role → 字串(§4) |
| 取 token | `get_access_token() -> str` | bff | 供 api_client 帶 Bearer;經 [`state.get_token()`](app-skeleton.md#71-libstatepy-helper-契約) 讀 `session_state["access_token"]` |
| 換 token | `refresh_token() -> str` | bff | 重呼 introspection、經 `state.set_token()` 回寫、回傳新值;失敗拋 `NotAuthenticated` |
| 取 cookie | `raw_cookie() -> Optional[str]` | bff | 從 `st.context.cookies` 取加密 session cookie 原值,供 introspection 轉發 |
| 登出 | `logout() -> None` | bff | 呼叫 BFF logout + 清狀態/快取(見 auth-flow §4.5) |

- `get_access_token` / `refresh_token` / `raw_cookie` 即 [api-client §4–§5](api-client.md#4-單次呼叫流程共用) 的 auth 接縫;api_client **只消費**,token 生命週期單點集中於此。
- mock 模式下 `get_access_token` / `refresh_token` / `raw_cookie` **不應被呼叫**(api 資料源需 `bff`,見 api-client §1 旗標交互);若誤呼 → 拋 `RuntimeError("AUTH_MODE=mock 無 token")`,凸顯設定錯誤。

---

## 3. `resolve_actor()` 兩模式行為

| `AUTH_MODE` | 行為 | 回傳 |
|---|---|---|
| `mock` | 讀 `session_state["actor"]`;無則預設 `Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN)` 並寫回 | **恆有** `Actor` |
| `bff` | `raw = raw_cookie()`;無 → `None`。有 → introspection(§4)→ 解析為 `Actor`;401/失敗 → 清狀態回 `None` | `Actor` 或 `None` |

- **mock**:身分由[開發用切換器](app-skeleton.md#4-身分解析resolve_actor兩模式單一出口)寫入 `session_state["actor"]`;`resolve_actor` 只讀不打任何網路。種子預設 `alice/user`。
- **bff**:流程與快取細節見 [auth-flow §4.2 / §4.6](auth-flow.md#42-每次-rerun-的身分辨識核心流程);`resolve_actor` 內部呼叫 introspection 並落 `Actor` + `access_token` + `token_expires_at` 到 `session_state`。
- **關鍵**:`app.py` 只看回傳值,不關心模式(骨架 §4)。

---

## 3a. `require_auth()` 頁面守衛（安全兜底層）

`app.py` 的 auth gate 是**正常路徑**的守衛；`require_auth()` 是各頁面先頭呼叫的**兜底層**，防禦以下罕見但可能發生的情境：

- Streamlit MPA 執行模型中，`st.navigation().run()` 實際上由 script runner 在 `app.py` 執行後另行呼叫 `page.run()`，若頁面拋出 `NotAuthenticated` 異常，Streamlit runtime 會直接顯示錯誤，`app.py` 的 `try/except` 無法捕捉。
- session 在兩個 rerun 間過期，頁面開始執行時 `actor` 已被清除。

**行為定義**

| 條件 | 行為 |
|---|---|
| `use_mock=True`（mock 模式） | 直接回傳，不做任何檢查 |
| `use_mock=False` 且 `session_state["actor"]` 已設 | 直接回傳，正常執行頁面 |
| `use_mock=False` 且 `session_state["actor"]` 未設 | `st.markdown(<meta refresh>)` 跳轉 `BFF_BASE_URL + BFF_LOGIN_PATH`，接著 `st.stop()` |

**呼叫位置**：四個業務頁（`data_management.py`、`realtime_monitor.py`、`analytics.py`、`system_management.py`）的**頁面主體最頂端**（import 之後、任何 `st.*` 呼叫之前）。

---

## 4. bff:introspection 解析與 role / grade 映射

- **introspection 呼叫**:`GET {BFF}/api/auth/session`,以 `raw_cookie()` 轉發 cookie(api-client `auth="cookie"`);回應 `{ user, role, grade, accessToken, expiresAt, csrfToken }`(auth-flow §3.1、015 §2.3)。`grade` 對應後端 JWT grade claim，為 **int**（admin → `0`/`50`/`100`/`999` = viewer/editor/super_admin/root；見 `AdminRole` 常數）。
- **落地**:`session_state["actor"] = Actor(user.name, map_role(role), grade=int(grade))`、`["access_token"] = accessToken`、`["token_expires_at"] = expiresAt`、`["csrf_token"] = csrfToken`。**`grade` 必須以 int 帶入**,否則 `can_write` 判不到 viewer（grade=0，存取 gate 失效）。
- **role 映射** `map_role`:後端沿用前端 `Role` enum 數值;預設 `1 → "admin"`、其餘 → `"user"`。**確切數值待與前端 `lib/session/types` 對齊**(§7)。
- **快取**:以 `st.cache_data`(TTL 30–60s、不超過 `expiresAt`)包住「cookie 原值 → introspection 結果」;401 / 登出 / refresh 後主動清快取(auth-flow §4.6)。

---

## 5. `NotAuthenticated` 例外

- 定義於 **`lib/models.py`**(與 `RecordNotFound`/`PermissionDenied`/`ValidationError` 同處,集中管理域例外)。
- 觸發:`refresh_token()` 重試後仍 401、或 introspection 判定 session 失效。
- 處理:`app.py` / api_client 上層攔到 → 清 `session_state`(actor/token)+ 清快取 → 導向主前端登入(auth-flow §4.4)。

---

## 6. session_state 契約(本模組寫入)

沿用[應用骨架 §7](app-skeleton.md#7-session_state-契約單一真相),本模組負責:

| Key | 寫入時機 | 模式 |
|---|---|---|
| `actor` | `resolve_actor` 成功 / 開發切換器 | 全部 |
| `access_token` | introspection / `refresh_token` | bff |
| `token_expires_at` | introspection / `refresh_token` | bff |
| `csrf_token` | introspection(`resolve_actor` 成功) | bff |

- 登出 / 401 → 清上述全部 key 與 introspection 快取。
- token / csrfToken **只存記憶體**,不寫檔、不落 log(auth-flow §7.2)。

---

## 7. 相依 / 待確認

- [ ] **role 數值對應**:`map_role` 的確切整數值需對齊前端 `Role` enum(`ADMIN`/`USER`);目前預設 `1→admin`。
- [x] **登出 CSRF**:已定案(2026-07-18)。csrfToken 由 introspection 一併回傳(`resolve_actor` 落 `state.set_csrf`)，`_do_logout_bff()` 從 `state.get_csrf()` 取用；不需額外打 `/api/csrf`（見 015 §7.1A）。
- [ ] **cookie 名稱**:`raw_cookie()` 讀的 cookie 名(如 `streamsight_session`)需與前端一致,放 `lib/config.py`。
- [x] **型別統一**:全專案身分型別為 `Actor`,`Identity` 廢除(§1)。
- [x] **auth 接縫**:`get_access_token`/`refresh_token`/`raw_cookie` 契約定於本檔,api_client 只消費。

---

## 8. 可測試性 / TDD

純邏輯 mock cookie / mock introspection,不打真後端;放 `tests/unit/test_auth.py`:

### mock 分支(骨架階段即可)
1. `resolve_actor()` 無 `session_state["actor"]` → 回 `Actor("alice","admin",grade=AdminRole.SUPER_ADMIN)` 並寫回（mock 種子預設 super_admin=100，確保初次開啟可看全部頁面）。
2. `session_state["actor"]` 已設(如切換器選 admin)→ 原樣回傳。
3. mock 下呼 `get_access_token()` → `RuntimeError`。

### `require_auth()` 守衛（§3a）
A. mock 模式：呼叫後不觸發 `st.stop()`（一律通過）。
B. bff 模式 + `session_state["actor"]` 已設：不觸發重導，不呼叫 `st.stop()`。
C. bff 模式 + `session_state["actor"]` 未設：輸出 `<meta refresh>` 並呼叫 `st.stop()`。

### bff 分支(接 API 階段)
4. `map_role(1)→"admin"`、`map_role(0)→"user"`、未知→`"user"`。
5. `resolve_actor()`:無 cookie → `None`(不打網路)。
6. 有 cookie + introspection 200 → 回 `Actor(grade=int(grade))`,並落 `access_token`/`token_expires_at`。
7. introspection 401 → 回 `None`,清狀態。
8. `refresh_token()`:200 → 回新 token 並回寫;再 401 → 拋 `NotAuthenticated`。
9. `raw_cookie()`:能從(mock)`st.context.cookies` 取值;無則 `None`。

> 依 CLAUDE.md,逐一先寫失敗測試再補實作。骨架階段先做 1–3(mock 分支);4–9 於接 bff 階段。

---

## 9. 檔案與掛載

```
lib/
├── auth.py         # resolve_actor / map_role / get_access_token / refresh_token / raw_cookie / logout
├── models.py       # Actor + NotAuthenticated(§1、§5)
├── api_client.py   # 消費 auth 接縫(§2)
├── state.py        # session_state 讀寫 helper(§6)
└── config.py       # BFF base URL、cookie 名、快取 TTL、role 對應
app.py              # 呼叫 resolve_actor()(骨架 §3)
tests/unit/test_auth.py
```

> 於 [應用骨架 §6 lib 分層](app-skeleton.md#6-lib-分層總表單一入口地圖) 中 `lib/auth.py` 的詳規即本檔。
