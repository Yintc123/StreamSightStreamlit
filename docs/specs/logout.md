# 規格：TopBar 登出按鈕功能接線

對齊 `auth-flow.md §4.5`——TopBar 右上角「登出」按鈕目前只是靜態 HTML，本規格定義完整接線方案，使其實際觸發後端登出流程。

- 關聯：[認證流程 §4.5](auth-flow.md#45-登出)、[TopBar 規格](topbar-cms-link.md)、[Auth 模組](auth.md)、[設定模組](config.md)
- 狀態：**已實作**（2026-07-19）

> **模式旗標更正**：本專案實際以 `USE_MOCK`（`settings.use_mock`）區分 mock / bff，
> 並無獨立的 `AUTH_MODE` 設定；下文原草稿的 `AUTH_MODE=mock` / `AUTH_MODE=bff`
> 分別對應 `USE_MOCK=true` / `USE_MOCK=false`。

---

## 1. 現況（as-is）

`lib/topbar.py` 目前產生的登出元素：

```html
<button class="ss-topbar__sysitem" type="button">登出</button>
```

**問題**：`onclick="..."` 在 Streamlit `st.markdown(unsafe_allow_html=True)` 渲染管線中靜默失效（React 需要 function reference，字串屬性被忽略，見 [topbar-cms-link.md §3](topbar-cms-link.md#3-連結開啟方式target_self)）。此按鈕按下後什麼都不發生。

`lib/auth.py` 的 `logout()` 函式已完整實作（mock 清狀態 / bff POST BFF + 清狀態），只缺 UI 觸發的接線。

---

## 2. 技術方案：`<a href="?logout=1">` + `app.py` 查詢參數偵測

### 2.1 為何用 `<a>` 而非 `<button onclick>`

Streamlit 1.50+ 以 `react-markdown` 渲染 `st.markdown()` 內容。`onclick` 字串屬性被靜默忽略；`href` 屬性則由自訂 `<a>` 元件正確處理，搭配 `target="_self"` 可強制同分頁導航（同 topbar-cms-link 品牌連結的處理）。

### 2.2 接線機制

```
使用者點「登出」
  → <a href="?logout=1" target="_self">
  → 瀏覽器導航至 ?logout=1
  → Streamlit rerun（帶 query param）
  → app.py 在 resolve_actor() 之後偵測 st.query_params["logout"]
  → 呼叫 auth.logout()
  → 導向 Next.js 登入頁（bff 模式）或清除 param rerun（mock 模式）
```

`?logout=1` 為攔截訊號，**不代表使用者已登出**；登出動作由 Python 端執行後才生效。

---

## 3. 行為規格

### 3.1 BFF 模式（`USE_MOCK=false`）

| 步驟 | 執行位置 | 說明 |
|---|---|---|
| 1 | `resolve_actor()` | 正常 introspection（session 仍有效），CSRF token 寫入 `session_state` |
| 2 | `app.py` | 偵測 `st.query_params.get("logout") == "1"` |
| 3 | `auth.logout()` | POST `{bff_base_url}{bff_logout_path}`，帶 cookie + `X-CSRF-Token` + `Origin`；try/finally 確保本地 session_state 與快取一定清除 |
| 4 | `app.py` | `<meta http-equiv="refresh" content="0; url={login_url}">` + `st.stop()` |

**重點**：偵測在 `resolve_actor()` 之後，確保 CSRF token 已在 `session_state`（auth-flow §7.3）。

**錯誤處理**：`logout()` 已以 `try/finally` 包住 BFF 呼叫；BFF 不回應或 CSRF 遺失時，本地狀態依然清除，使用者依然被導向登入頁（最佳努力語意，auth-flow §4.5）。

### 3.2 Mock 模式（`USE_MOCK=true`）

Mock 模式無 BFF 也無登入頁可跳轉。`auth.logout()` 已只做 `state.clear_auth()`；下次 rerun `resolve_actor()` 會重建預設 mock actor，等同「換回預設角色」。

| 步驟 | 執行位置 | 說明 |
|---|---|---|
| 1 | `app.py` | 偵測 `st.query_params.get("logout") == "1"` |
| 2 | `auth.logout()` | `state.clear_auth()`（mock 模式實作） |
| 3 | `app.py` | `st.query_params.clear()` → `st.rerun()` |

Mock 模式登出後會立刻以預設角色（`SUPER_ADMIN alice`）重新進入，這是開發環境的預期行為。

---

## 4. 模組變更清單

| 檔案 | 變更 |
|---|---|
| `lib/topbar.py` | 將 `<button>登出</button>` 改為 `<a class="ss-topbar__logout" href="?logout=1" target="_self">登出</a>` |
| `app.py` | 在 `resolve_actor()` 之後、`render_topbar()` 之前，插入登出偵測與處理邏輯 |
| `styles/main.css` | 確保 `.ss-topbar .ss-topbar__logout` 無底線、顯示正確（CSS specificity 需 ≥ 0,2,0，同 topbar-cms-link §6） |
| `tests/unit/test_topbar.py` | 新增 2 個測試（§5.1） |
| `tests/app/test_app_skeleton.py` | 新增 3 個測試（§5.2） |

### 4.1 `lib/topbar.py` 關鍵片段

```python
# 舊：
'<button class="ss-topbar__sysitem" type="button">登出</button>'

# 新（同時掛 ss-topbar__sysitem 複用既有字級 / hover / dark 樣式）：
'<a class="ss-topbar__logout ss-topbar__sysitem" href="?logout=1" target="_self">登出</a>'
```

`_build_topbar_html` 簽名與其他參數不變。

### 4.2 `app.py` 登出偵測插入點

```python
actor = resolve_actor()  # ③ 身分解析（不變）

if actor is None:        # ④ 未登入→跳轉（不變）
    ...

# ④′ 登出偵測（新增，必須在 resolve_actor 之後）
if st.query_params.get("logout") == "1":
    from lib.auth import logout as _logout
    _logout()
    _s = get_settings()
    if _s.use_mock:
        st.query_params.clear()
        st.rerun()
    else:
        _login_url = f"{_s.bff_base_url}{_s.bff_login_path}"
        st.markdown(
            f'<meta http-equiv="refresh" content="0; url={_login_url}">',
            unsafe_allow_html=True,
        )
        st.stop()

if get_settings().use_mock:  # ⑤ 開發切換器（不變）
    ...
```

---

## 5. TDD 測試計畫

### 5.1 `tests/unit/test_topbar.py`（新增 2 個，已實作）

```python
def test_logout_is_anchor_not_button(actor):
    """登出元素為 <a>（onclick 在 st.markdown 的 react-markdown 管線中靜默失效）。"""
    html = _build_topbar_html(actor)
    assert '<a class="ss-topbar__logout' in html   # 可同時掛 ss-topbar__sysitem 複用樣式
    assert '<button class="ss-topbar__sysitem" type="button">登出</button>' not in html


def test_logout_href_and_target(actor):
    """登出 <a> 帶 href='?logout=1' 與 target='_self'（同分頁導航觸發 rerun）。"""
    html = _build_topbar_html(actor)
    idx = html.index("ss-topbar__logout")
    segment = html[idx: idx + 200]
    assert 'href="?logout=1"' in segment
    assert 'target="_self"' in segment
```

> 原 `test_logout_button_is_button_element`（斷言登出為 `<button>`）已作廢——
> 該設計正是登出無反應的根因。

### 5.2 `tests/app/test_app_skeleton.py`（新增 3 個，已實作）

> **AppTest 限制（實測發現，影響測試寫法）**：
> 1. app 端 `st.query_params.clear()` **不會寫回**測試端的 `at.query_params`，
>    且 AppTest 處理內部 rerun 時會重新注入 param——mock 登出的「清 param → rerun」
>    無法在單一 `at.run()` 內觀察完整結果。
> 2. 故 mock 測試以 **spy** 驗證 `auth.logout()` 被呼叫（接線正確性），
>    清狀態行為由 `tests/unit/test_auth.py` 的 7 個 logout 單元測試保證；
>    再手動移除 param 模擬瀏覽器 URL 已更新後驗證正常重進。
> 3. 找 topbar HTML 需以 `'class="ss-topbar"'` 匹配——`"ss-topbar"` 會先匹配到
>    注入的 `<style>` 區塊。

```python
def test_logout_link_present_in_topbar():
    """TopBar HTML 中包含 ?logout=1 連結（mock 模式）。"""
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    topbar_html = next(m.value for m in at.markdown if 'class="ss-topbar"' in m.value)
    assert "?logout=1" in topbar_html


def test_logout_param_calls_logout_in_mock(monkeypatch):
    """mock 模式帶 ?logout=1：auth.logout() 被呼叫；param 清除後正常以預設角色重進。"""
    called = {"n": 0}

    def _spy_logout():
        from lib import state
        called["n"] += 1
        state.clear_auth()

    monkeypatch.setattr("lib.auth.logout", _spy_logout)

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.query_params["logout"] = "1"
    at.run()
    assert not at.exception
    assert called["n"] >= 1                          # 接線生效

    if "logout" in at.query_params:                  # 模擬 URL param 已被 clear()
        del at.query_params["logout"]
    at.run()
    assert not at.exception
    assert "actor" in at.session_state               # 預設 mock actor 重建
    assert "資料分析" in [t.value for t in at.title]


def test_logout_param_redirects_to_login_in_bff(monkeypatch):
    """bff 模式帶 ?logout=1：呼叫 _do_logout_bff 後 meta refresh 導向登入頁。

    patch lib.auth 模組內部函式（raw_cookie / _introspect / _do_logout_bff）——
    resolve_actor / logout 於呼叫時查模組屬性，monkeypatch 可靠生效
    （patch app.py 的頂層 import 綁定則不可靠）。
    """
    monkeypatch.setenv("USE_MOCK", "0")
    monkeypatch.setenv("BFF_BASE_URL", "http://localhost:3000")

    called = {"logout_bff": 0}
    mock_data = {
        "user": {"id": "u_1", "name": "alice"},
        "role": 1,
        "adminRole": "super_admin",
        "accessToken": "tok",
        "expiresAt": 9999999999000,
        "csrfToken": "csrf-abc",
    }
    monkeypatch.setattr("lib.auth.raw_cookie", lambda: "cookie-val")
    monkeypatch.setattr("lib.auth._introspect", lambda: mock_data)
    monkeypatch.setattr(
        "lib.auth._do_logout_bff",
        lambda: called.__setitem__("logout_bff", called["logout_bff"] + 1),
    )

    at = AppTest.from_file(APP_PATH)
    at.run()
    at.query_params["logout"] = "1"
    at.run()
    assert not at.exception
    assert called["logout_bff"] == 1
    markdowns = [m.value for m in at.markdown]
    assert any("refresh" in m and "login" in m for m in markdowns)
```

> 注意：AppTest 不真正執行瀏覽器導航；meta refresh 的存在已足以驗證邏輯正確。

---

## 6. 樣式注意事項

登出 `<a>` 同時掛 `ss-topbar__sysitem`，字級 / padding / hover 底色 / dark 模式
均複用既有規則；另需明確覆蓋 `.stMarkdownContainer a` 的連結色與底線
（含 `:visited`，specificity 0,2,0 > 0,1,1）。

```css
/* styles/main.css — 已實作 */
.ss-topbar .ss-topbar__logout,
.ss-topbar .ss-topbar__logout:hover,
.ss-topbar .ss-topbar__logout:visited {
    text-decoration: none;
    color: rgba(15, 23, 42, 0.66);   /* ink-AA，同 sysitem */
    cursor: pointer;
}

html[data-theme="dark"] .ss-topbar .ss-topbar__logout,
html[data-theme="dark"] .ss-topbar .ss-topbar__logout:hover,
html[data-theme="dark"] .ss-topbar .ss-topbar__logout:visited {
    color: rgba(230, 237, 246, 0.72);  /* dark ink-AA，同 sysitem */
}
```

---

## 7. 不在本規格範圍

- `logout()` 本身的 BFF 呼叫細節：已定義於 [auth-flow §4.5](auth-flow.md#45-登出) 與 `lib/auth.py`，不重複。
- CSRF token 取得流程：已定義於 [auth-flow §7.3](auth-flow.md#73-csrf)。
- ThemeToggle 實作。
- 多分頁登出（Single Sign-Out 全系統驗證）：屬 E2E 範圍，非本 Streamlit 端規格。

---

## 8. 相關文件

- [認證流程規格 §4.5](auth-flow.md#45-登出)（BFF logout 端點契約、CSRF 要求）
- [TopBar 品牌連結規格](topbar-cms-link.md)（`target="_self"` 機制說明）
- `lib/auth.py:logout()`（已實作的登出邏輯）
- `lib/topbar.py:_build_topbar_html()`（被修改的 HTML 產生函式）
