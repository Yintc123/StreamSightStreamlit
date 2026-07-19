# 規格：側欄寬度 cookie 同步（sidebar_width）

狀態：**Streamlit 端已實作（2026-07-19）**（v0.2；跨 app 手動驗收待 Frontend 019 實作與根 `.env` 開關啟用）
姊妹規格：Frontend 端 [`StreamSightFrontend/docs/specs/019-sidebar-width-cookie.md`](../../../StreamSightFrontend/docs/specs/019-sidebar-width-cookie.md)
相關：[`theme-toggle.md`](./theme-toggle.md)（cookie / client-side JS 注入前例）、[設計系統](./design-system.md)

Streamlit 1.50 原生側欄可拖曳調寬，且**已會**把寬度存進本 origin 的
`localStorage['sidebarWidth']`（拖曳結束、雙擊把手重設時寫入；載入時讀取還原）。
但 localStorage 以 origin 為界，與 Next.js CMS（`localhost:3000`）互不相通。
本規格以注入 JS 將該值**橋接到 `sidebar_width` cookie**（同 `theme` cookie 手法），
讓兩個 app 的左欄共用同一個寬度。

---

## 1. 現況（實查 2026-07-19，Streamlit 1.50）

| 事實 | 出處 | 意義 |
|---|---|---|
| 側欄寬度：預設 `256`、最小 `200`、最大 `600` | stSidebar computed style 實測（Frontend spec 016 §4.3） | 與 CMS 端 `SIDEBAR_MIN/MAX/DEFAULT_WIDTH` 同值域，cookie 值免換算 |
| 原生持久化：`localStorage.setItem('sidebarWidth', …)`，拖曳結束 / 雙擊重設時寫；mount 時 `getItem` 還原 | `streamlit/static/static/js/index.*.js` bundle 實查 | 我們**不必**自己做「記住寬度」；只需橋接 localStorage ⇄ cookie |
| `components.html` iframe 為 srcdoc 同源，可存取 `window.parent`（theme JS 已依賴此） | `lib/theme.py` `_THEME_JS` 等 | 注入的 JS 可讀寫父頁 cookie / localStorage、可收到父頁的 `storage` 事件 |
| `_FORCE_LIGHT_JS` 前例：sessionStorage guard + `win.location.reload()` 修正 localStorage 後重載 | `lib/theme.py` | inbound 同步（cookie → localStorage → reload）沿用同一 pattern |
| `theme` cookie：`Max-Age` 1 年、`Path=/`、`SameSite=Lax`、prod `Secure`、host-only | `lib/theme.py` `build_theme_cookie_string` | `sidebar_width` 屬性照抄 |

---

## 2. 跨 repo cookie 契約（與 Frontend spec 019 §3.1 逐字一致）

| 項目 | 值 |
|---|---|
| 名稱 | `sidebar_width` |
| 值 | 整數 px 的十進位字串（如 `"320"`），值域 `[200, 600]` |
| 屬性 | `Max-Age=31536000`（1 年）、`Path=/`、`SameSite=Lax`、prod 加 `Secure`；`httpOnly:false`；**不設 `Domain`**（host-only，同 `theme`） |
| 缺省 / 非法值 | 各 app 走自己的退路（本端＝不動 Streamlit 原生行為），**不寫回修正** |
| 衝突解決 | last-write-wins |
| 登出 | 不清（偏好獨立於 session） |

---

## 3. 設計

### 3.1 架構決策：橋接原生儲存，不重做側欄

Streamlit 側欄寬度由其 React 內部狀態管理，外部無 API。可行介入點只有它的
持久化介面 `localStorage['sidebarWidth']`：

- **inbound（cookie → Streamlit）**：載入時讀 cookie，與 `sidebarWidth` 不一致 →
  覆寫 localStorage 後 `reload()` 讓 Streamlit 重讀（mount 時才讀，改值不會熱生效）。
- **outbound（Streamlit → cookie）**：Streamlit 拖曳結束寫 localStorage → 父頁的寫入會對
  **同源 iframe 觸發 `storage` 事件** → 注入 JS 在事件中把新值寫進 cookie。
  免輪詢、免 ResizeObserver（也天然涵蓋雙擊重設）。

### 3.2 注入 JS（`_SIDEBAR_SYNC_JS`）

```js
(function () {
  var win = window.parent;
  try {
    var KEY = 'sidebarWidth', GUARD = 'ss-sidebar-sync';
    var SECURE = "__SECURE__";  // json.dumps 填入（同 theme JS）
    function valid(v) { return Number.isInteger(v) && v >= 200 && v <= 600; }
    function readCookie() {
      var m = win.document.cookie.match(/(?:^|;\s*)sidebar_width=(\d+)(?:;|$)/);
      var v = m ? parseInt(m[1], 10) : NaN;
      return valid(v) ? v : null;
    }
    function writeCookie(v) {
      win.document.cookie =
        'sidebar_width=' + v + '; Max-Age=31536000; Path=/; SameSite=Lax' + SECURE;
    }
    var fromCookie = readCookie();
    var stored = parseInt(win.localStorage.getItem(KEY) || '', 10);

    // inbound：cookie 有值且與 localStorage 不一致 → 覆寫 + reload（guard 防迴圈）
    if (fromCookie !== null && fromCookie !== stored) {
      if (!win.sessionStorage.getItem(GUARD)) {
        win.sessionStorage.setItem(GUARD, '1');
        win.localStorage.setItem(KEY, String(fromCookie));
        win.location.reload();
        return;
      }
    } else {
      win.sessionStorage.removeItem(GUARD);  // 已一致 → 允許本分頁未來再同步
    }

    // 建檔：cookie 缺省而本地已有合法寬度 → 以本地值建立 cookie
    if (fromCookie === null && valid(stored)) writeCookie(stored);

    // outbound：父頁寫 localStorage（拖曳結束 / 雙擊重設）→ storage 事件 → 寫 cookie
    window.addEventListener('storage', function (e) {
      if (e.key !== KEY || !e.newValue) return;
      var v = parseInt(e.newValue, 10);
      if (valid(v)) writeCookie(v);
    });
  } catch (e) {}
})();
```

行為要點：

- **reload 只發生在首載且值不一致**的瞬間（頁面剛載入、使用者尚未互動），成本同
  `_FORCE_LIGHT_JS` 既有取捨；值一致時清掉 guard，讓長開分頁下次 rerun 仍可接收新 cookie。
- **localStorage 空（首訪）而 cookie 有值**：`stored` 為 `NaN`，`fromCookie !== stored`
  恆真 → 走 inbound 覆寫 + reload 採用 cookie 值。這是期望行為（CMS 先設定、
  Streamlit 首訪即同寬），非邊界 bug。
- **不寫回修正**：cookie 非法 / 缺省不主動建立預設值（契約 §2），避免兩端啟動互寫。
- 每次 rerun 重注入為冪等：inbound 判斷冪等；`storage` listener 隨舊 iframe 銷毀，不累積。

### 3.3 Python 側（`lib/sidebar.py`，新檔）

| 項目 | 內容 |
|---|---|
| 常數 | `SIDEBAR_COOKIE = "sidebar_width"`、`SIDEBAR_MIN_WIDTH = 200`、`SIDEBAR_MAX_WIDTH = 600`、`SIDEBAR_DEFAULT_WIDTH = 256`（**僅文件化原生預設值**，不參與任何邏輯——契約 §2 不寫回修正，實作不得加「缺省時寫入預設」）、`SIDEBAR_COOKIE_MAX_AGE = 31_536_000` |
| `parse_sidebar_width(raw) -> int \| None` | 純函式：十進位整數字串且在 `[200, 600]` → int；其餘（`None` / 空 / 非數字 / 越界 / 浮點）→ `None`。與 JS `valid()` 同語義，供測試錨定契約 |
| `build_sidebar_sync_js(is_prod=False) -> str` | 回傳 `_SIDEBAR_SYNC_JS`，`"__SECURE__"` 以 `json.dumps` 填入（prod → `"; Secure"`），同 `build_theme_toggle_js` 手法 |
| `inject_sidebar_sync_js(enabled=False, is_prod=False) -> None` | `enabled=False` → 不注入（no-op）；`True` → `components.html(f"<script>{js}</script>", height=0)` |

### 3.4 功能開關與接線

- `lib/config.py`：`enable_sidebar_width_sync: bool = False`（0/1，讀法同 `enable_theme_toggle`；
  依 `APP_ENV` 設定類佈署，見 [config 規格](./config.md)）。
- 根 `docker-compose.yml` / `.env`：`ENABLE_SIDEBAR_WIDTH_SYNC=1`（與主題切換同步啟用；
  **改 .env 後需重啟 Streamlit**——`get_settings` 有 `lru_cache`）。
- `app.py`：於 ⑦′ `idle.inject_idle_js()` 之後、`build_pages` 之前加
  **⑦″** `inject_sidebar_sync_js(enabled, is_prod)`（⑧ 已被「路由」佔用，勿撞號；
  注入越早，inbound reload 越無感）。`enabled` / `is_prod` 沿用 ⑥⑦ 既有的
  `get_settings().enable_sidebar_width_sync` 與 `_is_prod` 取值方式。
- 開關定位為 **kill-switch**：橋接依賴 Streamlit 內部 key（§5 風險），升版若壞可即關，
  行為退回「各自記住」（無功能損失，只失去跨 app 同步）。

---

## 4. 測試規格（TDD，先寫失敗測試）

既有測試基建可直接沿用，**不必自建**：

- `tests/conftest.py` 已有 autouse fixture 於每測前 `get_settings.cache_clear()`——config
  測試用 `monkeypatch.setenv` 即可，不需手動清 cache。
- inject 類測試沿用 `tests/unit/test_theme.py` 的 `_capture_injected_html` 手法
  （`monkeypatch.setattr(components, "html", …)` 捕捉 body），驗證注入內容與 `height=0`。

### `tests/unit/test_sidebar.py`（新）

| 測試 | 斷言 |
|---|---|
| `parse_sidebar_width` happy | `"320"` → `320`；邊界 `"200"`/`"600"` 通過 |
| `parse_sidebar_width` edge | `None`/`""`/`"abc"`/`"199"`/`"601"`/`"320.5"` → `None` |
| `build_sidebar_sync_js` dev | 含 `sidebar_width`、`sidebarWidth`、`Max-Age=31536000`；不含 `Secure` |
| `build_sidebar_sync_js` prod | 含 `; Secure`（`json.dumps` 注入，無引號洩漏） |
| `inject_sidebar_sync_js` 關 | `enabled=False` → 不呼叫 `components.html`（mock 驗證） |
| `inject_sidebar_sync_js` 開 | `enabled=True` → 注入一次、`height=0` |

### `tests/unit/test_config.py`（增）

- `ENABLE_SIDEBAR_WIDTH_SYNC` 缺省 → `False`；`"1"` → `True`（範本：既有
  `test_enable_theme_toggle_defaults_false` / `test_enable_theme_toggle_can_be_set_true`）。

### 手動驗收（跨 app，無法自動化）

1. CMS（:3000）拖寬左欄 → 重整 Streamlit（:8501）→ 側欄同寬。
2. Streamlit 拖寬 → 切回 CMS 分頁（focus）→ 左欄同寬（Frontend 019 §5）。
3. Streamlit 雙擊把手重設 256 → cookie 同步為 256。
4. 清 cookie 重載 → 兩端各自維持原行為（退路正確、無 reload 迴圈）。

---

## 5. 風險與取捨（評估結論）

| 風險 | 緩解 |
|---|---|
| 依賴 Streamlit **內部** localStorage key `sidebarWidth`（非公開 API），升版可能改名 / 改行為 | 1.50 bundle 已實查；升版檢查清單加「重驗 sidebarWidth key」；壞掉時 outbound 靜默失效、inbound 不觸發——**退化為各自記住，app 本體無損**；kill-switch 可即關 |
| `storage` 事件依賴 components iframe 與父頁同源 | theme JS 已依賴 `window.parent.document`（同源成立）；若未來 Streamlit 改 sandbox，退場方案為 ResizeObserver + debounce（OQ-1） |
| inbound `reload()` 打斷載入 | 僅首載且值不一致時觸發一次（尚未互動）；guard 防迴圈；與 `_FORCE_LIGHT_JS` 同既有取捨 |
| host-only cookie：雲端子網域（`*.streamsight.local`）不共用 | 與 `theme` cookie 同限制；本機 / 同 host 拓撲有效；跨子網域屬另案（Frontend 019 OQ-2） |
| 兩端同時拖曳的競態 | last-write-wins（§2），偏好類資料可接受 |

**不採的替代方案**：postMessage 橋（需雙端常駐 listener + 對時序，複雜度高於 cookie）；
反向代理收斂同 origin（部署架構級改動，超出需求比例）；改造側欄元件（Streamlit 無擴充點）。

---

## 6. 不在本規格範圍

- 收合態同步（Streamlit 原生收合不持久化，無可橋接的儲存）。
- CMS 端的 cookie 讀寫與遷移 → Frontend spec 019。
- `theme` / `sidebar_width` 的 `Domain` 跨子網域議題。

## 7. 相關文件

- Frontend [spec 019](../../../StreamSightFrontend/docs/specs/019-sidebar-width-cookie.md)（cookie 契約鏡像、CMS 端實作）
- [`theme-toggle.md`](./theme-toggle.md) §8 Cookie 規格（屬性前例）
- [config 規格](./config.md)（`APP_ENV` 設定類與 env 佈署）

---

## 變更紀錄

| 版本 | 日期 | 變更 |
|---|---|---|
| 0.1 | 2026-07-19 | 初版規劃：以注入 JS 橋接 Streamlit 原生 `localStorage['sidebarWidth']` ⇄ `sidebar_width` cookie（inbound reload + outbound storage 事件）；`lib/sidebar.py` 純函式 + 注入器；`ENABLE_SIDEBAR_WIDTH_SYNC` kill-switch；TDD 與手動驗收計畫；風險評估。 |
| 0.2 | 2026-07-19 | 對齊實作前實查：接線編號修正為 ⑦″（⑧ 已被路由佔用）；`SIDEBAR_DEFAULT_WIDTH` 明訂僅文件化、禁寫回；§3.2 補「localStorage 空 + cookie 有值 → NaN 路徑走 inbound」說明；測試規格錨定既有基建（conftest autouse `cache_clear`、`_capture_injected_html` 手法、`test_enable_theme_toggle_*` 範本）。 |

---

最後更新：2026-07-19（v0.2，規劃中）
