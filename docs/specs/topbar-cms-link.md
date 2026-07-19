# 規格：TopBar 品牌 & 管理後台連結導向前端 /cms

對齊 StreamSightFrontend `CmsTopBar.tsx`——兩端 TopBar 的系統切換邏輯必須鏡像：
- 前端品牌 `StreamSight` → `<Link href="/cms">`（同分頁）
- 前端管理後台 → `<Link href="/cms">`（同分頁）
- Streamlit 品牌 `StreamSight` → `href="{cms_base_url}" target="_self"`
- Streamlit 管理後台 → `href="{cms_base_url}" target="_self"`

---

## 1. 最終狀態

| 元素 | 實作 | 對應前端 |
|---|---|---|
| 品牌 `.ss-topbar__brand` | `href="{cms_href}" target="_self"` | `<Link href="/cms">StreamSight</Link>` |
| 管理後台 `.ss-topbar__sysitem`（`<a>`） | `href="{cms_href}" target="_self"` | `<Link href="/cms">管理後台</Link>` |

> 兩個連結導向相同目標（前端 /cms），與 CmsTopBar.tsx 行為完全一致。

---

## 2. cms_base_url 語意 & 設定來源

`cms_base_url` 語意為**完整的 CMS 根路徑**，例如 `http://localhost:3000/cms`。

- 空字串 → 降回 `href="#"`（本機 fallback；正常情況不會發生，因 `bff_base_url` 永遠有預設值）。
- 測試以 `http://localhost:3000/cms` 作為代表值。

### 2.1 設定欄位 `bff_cms_path`（`lib/config.py`）

對齊現有的 BFF 路徑欄位慣例：

| 欄位 | 預設 | env 變數 |
|---|---|---|
| `bff_session_path` | `/api/auth/session` | `BFF_SESSION_PATH` |
| `bff_logout_path` | `/api/auth/logout` | `BFF_LOGOUT_PATH` |
| `bff_login_path` | `/login` | `BFF_LOGIN_PATH` |
| `bff_cms_path` | `/cms` | `BFF_CMS_PATH` |

### 2.2 `app.py` 組裝邏輯

```python
_s2 = get_settings()
_cms_url = f"{_s2.bff_base_url}{_s2.bff_cms_path}"   # 永遠傳，不分 mock/bff 模式
render_topbar(actor, cms_base_url=_cms_url)
```

`auth_mode` 條件已移除。理由：`bff_base_url` 在 mock 模式下仍有預設值（`http://localhost:3000`），連結永遠可用；若前端未啟動點擊後會看到 connection refused，比 `href="#"` 的無聲無息更清楚。

---

## 3. 連結開啟方式（`target="_self"`）

兩個連結均加 `target="_self"`，強制同分頁跳轉。

**為什麼需要明確加 `target="_self"`**：Streamlit 1.50 以 `react-markdown` 渲染 `st.markdown()` 內容，其自訂 `<a>` 元件的 target 邏輯為：

```javascript
target: N || "_blank"   // N = 元素的 target 屬性；未設則強制 _blank
```

不設 target 時，所有外部連結都會另開分頁。設 `target="_self"` 後，N 為真值，覆蓋預設，回到瀏覽器原生的同分頁導航。

**為什麼 `onclick` 無效**：`onclick="..."` 是字串屬性。Streamlit 將 HTML 節點轉成 React 元件時，事件處理器需為 function reference，字串版會被靜默忽略。

---

## 4. 變更範圍

| 檔案 | 變更 |
|---|---|
| `lib/config.py` | 新增 `bff_cms_path: str = "/cms"` |
| `lib/topbar.py` | 品牌與管理後台 `<a>` 均加 `target="_self"`；品牌 href 從 `"#"` 改為 `"{cms_href}"` |
| `app.py` | `_cms_url` 改用 `bff_cms_path`；移除 `auth_mode == "bff"` 條件，永遠傳 URL |
| `tests/unit/test_config.py` | 新增 1 個測試（§5） |
| `tests/unit/test_topbar.py` | 新增 4 個測試（§5） |
| `tests/app/test_app_skeleton.py` | 新增 1 個 app 層測試（§5） |
| `styles/main.css` | 新增雙類選擇器確保品牌 & 管理後台連結無底線（§6） |
| `docs/specs/design-system.md` | 更新品牌 href 說明 |
| `docs/specs/config.md` | 新增 `BFF_CMS_PATH` 欄位記錄 |

### `lib/topbar.py` 最終程式碼（關鍵片段）

```python
cms_href = cms_base_url if cms_base_url else "#"

# 品牌
f'<a class="ss-topbar__brand" href="{cms_href}" target="_self">Stream'
f'<span class="ss-topbar__accent">Sight</span></a>'

# 管理後台
f'<a class="ss-topbar__sysitem" href="{cms_href}" target="_self">管理後台</a>'
```

---

## 5. 測試規格

### 5.1 新增測試（共 6 個）

```python
# tests/unit/test_config.py
def test_bff_cms_path_default():
    """bff_cms_path 預設值為 '/cms'。"""
    s = get_settings()
    assert s.bff_cms_path == "/cms"


# tests/unit/test_topbar.py
def test_brand_href_from_base_url(actor):
    """cms_base_url 非空時，品牌 <a> 元素本身的 href 含有該 URL。"""
    html = _build_topbar_html(actor, cms_base_url="http://localhost:3000/cms")
    assert 'class="ss-topbar__brand" href="http://localhost:3000/cms"' in html


def test_brand_href_fallback_to_hash(actor):
    """cms_base_url 空字串時，品牌 <a> 的 href 降回 '#'。"""
    html = _build_topbar_html(actor, cms_base_url="")
    assert 'class="ss-topbar__brand" href="#"' in html


def test_brand_link_same_tab(actor):
    """品牌 <a> 有 target="_self"（覆蓋 Streamlit react-markdown 預設 _blank）。"""
    html = _build_topbar_html(actor, cms_base_url="http://localhost:3000/cms")
    idx = html.index('class="ss-topbar__brand"')
    assert 'target="_self"' in html[idx: idx + 200]


def test_cms_tab_link_same_tab(actor):
    """管理後台 <a> 有 target="_self"（同上）。"""
    html = _build_topbar_html(actor, cms_base_url="http://localhost:3000/cms")
    idx = html.index("管理後台")
    assert 'target="_self"' in html[max(0, idx - 250): idx]


# tests/app/test_app_skeleton.py
def test_topbar_cms_url_always_passed(monkeypatch):
    """mock 模式下，TopBar 仍傳入 bff_base_url+bff_cms_path 的 URL（不因 auth_mode=mock 降回 '#'）。"""
    monkeypatch.setenv("AUTH_MODE", "mock")
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert not at.exception
    markdowns = [m.value for m in at.markdown]
    topbar_html = next(m for m in markdowns if '<div class="ss-topbar">' in m)
    assert "localhost:3000/cms" in topbar_html
```

### 5.2 現有測試不需更動

- `test_brand_stream_text`、`test_brand_accent_span`：只驗文字，繼續通過。
- `test_cms_tab_href_from_base_url`、`test_cms_tab_href_fallback_to_hash`：管理後台 href 邏輯不變，繼續通過。
- 其餘測試：無影響。

---

## 6. 樣式注意事項

### 連結無底線

品牌與管理後台連結須明確消除底線。單類選擇器（`.ss-topbar__brand`，specificity 0,1,0）會被 Streamlit 全域的 `.stMarkdownContainer a`（0,1,1）覆蓋，故需用雙類選擇器提升至 0,2,0：

```css
.ss-topbar .ss-topbar__brand,
.ss-topbar .ss-topbar__brand:hover,
.ss-topbar .ss-topbar__brand:visited,
.ss-topbar .ss-topbar__sysitem,
.ss-topbar .ss-topbar__sysitem:hover {
    text-decoration: none;
}
```

---

## 7. 不在本規格範圍

- 深色模式 ThemeToggle 功能實作。
- 登出按鈕 CSRF / BFF 流程。

---

## 7. 相關文件

- [設計系統規格 §TopBar](design-system.md#頂部-nav-bar對齊-streamsightfrontend-cmstopbar)（CSS 樣式、元件結構）
- [設定模組 §3.3 BFF](config.md#33-bffnextjs——introspection-目標)（`BFF_BASE_URL` / `BFF_CMS_PATH` 來源）
- StreamSightFrontend `src/app/cms/CmsTopBar.tsx`（對齊來源）
