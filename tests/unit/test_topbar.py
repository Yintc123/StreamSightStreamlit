"""lib/topbar.py 的單元測試（TDD RED 先行）。

測試 _build_topbar_html(actor, cms_base_url) 這個純函式，確保產生的 HTML
對齊 StreamSightFrontend CmsTopBar 的每個元件。
"""
from __future__ import annotations

import pytest

from lib.models import Actor, AdminRole
from lib.topbar import _build_topbar_html


@pytest.fixture
def actor():
    return Actor("alice", "admin", grade=AdminRole.SUPER_ADMIN)


# ── 品牌 ──────────────────────────────────────────────────────────────────────

def test_brand_href_from_base_url(actor):
    """cms_base_url 非空時，品牌 <a> 元素本身的 href 含有該 URL（對齊 CmsTopBar.tsx <Link href="/cms">）。"""
    html = _build_topbar_html(actor, cms_base_url="http://localhost:3000/cms")
    assert 'class="ss-topbar__brand" href="http://localhost:3000/cms"' in html


def test_brand_link_same_tab(actor):
    """品牌 <a> 有 target="_self"（Streamlit react-markdown 預設 target=N||"_blank"，須明確覆蓋）。"""
    html = _build_topbar_html(actor, cms_base_url="http://localhost:3000/cms")
    idx = html.index('class="ss-topbar__brand"')
    surrounding = html[idx: idx + 200]
    assert 'target="_self"' in surrounding


def test_brand_href_fallback_to_hash(actor):
    """cms_base_url 為空字串時，品牌 <a> 元素本身的 href 降回 '#'（mock 環境安全預設）。"""
    html = _build_topbar_html(actor, cms_base_url="")
    assert 'class="ss-topbar__brand" href="#"' in html


def test_brand_stream_text(actor):
    """'Stream' 文字存在且不在 accent span 內。"""
    html = _build_topbar_html(actor)
    assert "Stream" in html


def test_brand_accent_span(actor):
    """'Sight' 包在 ss-topbar__accent span 裡（對齊 CmsTopBar text-brand 強調）。"""
    html = _build_topbar_html(actor)
    assert '<span class="ss-topbar__accent">Sight</span>' in html


# ── 系統切換 Nav ──────────────────────────────────────────────────────────────

def test_data_platform_tab_is_active(actor):
    """'資料平台' tab 有 ss-topbar__sysitem--active class（Streamlit IS 資料平台）。"""
    html = _build_topbar_html(actor)
    assert "ss-topbar__sysitem--active" in html
    # active class 與 '資料平台' 在同一個元素內
    idx = html.index("ss-topbar__sysitem--active")
    surrounding = html[max(0, idx - 100): idx + 200]
    assert "資料平台" in surrounding


def test_cms_tab_is_not_active(actor):
    """'管理後台' tab 本身沒有 ss-topbar__sysitem--active class。"""
    html = _build_topbar_html(actor)
    idx = html.index("管理後台")
    surrounding = html[max(0, idx - 200): idx + 50]
    assert "ss-topbar__sysitem--active" not in surrounding


def test_cms_tab_href_from_base_url(actor):
    """cms_base_url 非空時，'管理後台' href 含有該 URL。"""
    html = _build_topbar_html(actor, cms_base_url="http://localhost:3000/cms")
    assert "http://localhost:3000/cms" in html


def test_cms_tab_link_same_tab(actor):
    """管理後台 <a> 有 target="_self"（Streamlit react-markdown 預設 target=N||"_blank"，須明確覆蓋）。"""
    html = _build_topbar_html(actor, cms_base_url="http://localhost:3000/cms")
    idx = html.index("管理後台")
    before = html[max(0, idx - 250): idx]
    assert 'target="_self"' in before


def test_cms_tab_href_fallback_to_hash(actor):
    """cms_base_url 為空字串時，'管理後台' href 降回 '#'（mock 環境安全預設）。"""
    html = _build_topbar_html(actor, cms_base_url="")
    # href="#" 在管理後台的 <a> 元素裡
    idx = html.index("管理後台")
    surrounding = html[max(0, idx - 150): idx + 20]
    assert 'href="#"' in surrounding


# ── 右側：使用者名稱 ──────────────────────────────────────────────────────────

def test_username_appears_in_html(actor):
    """actor.username 出現在 HTML 中。"""
    html = _build_topbar_html(actor)
    assert "alice" in html


def test_username_xss_escaped():
    """username 含 HTML 特殊字元時須 escape，防止 XSS。"""
    evil = Actor('<script>alert(1)</script>', "admin")
    html = _build_topbar_html(evil)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_username_element_has_class(actor):
    """使用者名稱包在 ss-topbar__username class 的元素裡。"""
    html = _build_topbar_html(actor)
    assert "ss-topbar__username" in html
    idx = html.index("ss-topbar__username")
    surrounding = html[idx: idx + 200]
    assert "alice" in surrounding


# ── 右側：ThemeToggle（ENABLE_THEME_TOGGLE 開關控制）────────────────────────────

def test_theme_btn_hidden_when_toggle_disabled(actor):
    """ENABLE_THEME_TOGGLE=False 時，icon 不渲染（預設行為）。"""
    html = _build_topbar_html(actor, enable_theme_toggle=False)
    assert "ss-topbar__theme-btn" not in html


def test_theme_btn_shown_when_toggle_enabled(actor):
    """ENABLE_THEME_TOGGLE=True 時，icon 出現。"""
    html = _build_topbar_html(actor, enable_theme_toggle=True)
    assert "ss-topbar__theme-btn" in html


def _theme_btn_segment(html: str) -> str:
    """擷取 theme-btn <button>…</button> 片段（避免誤中其他元素）。"""
    idx = html.index("ss-topbar__theme-btn")
    return html[idx: html.index("</button>", idx)]


def test_theme_btn_interactive_when_toggle_enabled(actor):
    """啟用切換（theme-toggle.md §6.2.4）時按鈕可互動：不含 disabled。"""
    html = _build_topbar_html(actor, enable_theme_toggle=True)
    assert "disabled" not in _theme_btn_segment(html)


def test_theme_btn_has_initial_aria_pressed(actor):
    """啟用時按鈕帶初始 aria-pressed='true'（light 猜測，JS syncButton 校正）。"""
    html = _build_topbar_html(actor, enable_theme_toggle=True)
    assert 'aria-pressed="true"' in _theme_btn_segment(html)


# ── 右側：登出按鈕 ────────────────────────────────────────────────────────────

def test_logout_button_present(actor):
    """登出按鈕存在（元件一致性）。"""
    html = _build_topbar_html(actor)
    assert "登出" in html


# （原 test_logout_button_is_button_element 已作廢：<button onclick> 在
#   st.markdown 的 react-markdown 管線中靜默失效，登出改為 <a href="?logout=1">，
#   見 logout.md §2.1；新契約由下方「登出接線」測試覆蓋。）


# ── 整體結構 ──────────────────────────────────────────────────────────────────

def test_topbar_root_class(actor):
    """頂層容器有 ss-topbar class。"""
    html = _build_topbar_html(actor)
    assert 'class="ss-topbar"' in html


# ── 登出接線（logout.md §4.1）───────────────────────────────────────────────

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
