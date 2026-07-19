"""lib/topbar.py 的單元測試（TDD RED 先行）。

測試 _build_topbar_html(actor, cms_base_url) 這個純函式，確保產生的 HTML
對齊 StreamSightFrontend CmsTopBar 的每個元件。
"""
from __future__ import annotations

import pytest

from lib.models import Actor
from lib.topbar import _build_topbar_html


@pytest.fixture
def actor():
    return Actor("alice", "admin", grade="super_admin")


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


# ── 右側：ThemeToggle ─────────────────────────────────────────────────────────

def test_theme_toggle_has_aria_label(actor):
    """ThemeToggle 按鈕預設（dark）有 aria-label='切換為淺色'（對齊 ThemeToggle.tsx aria-label）。"""
    html = _build_topbar_html(actor)
    assert 'aria-label="切換為淺色"' in html


def test_theme_toggle_has_sun_svg(actor):
    """ThemeToggle 預設（dark）顯示月亮 SVG（對齊 ThemeToggle.tsx dark mode MoonPaths）。"""
    html = _build_topbar_html(actor)
    assert "M21 12.79" in html


def test_theme_toggle_dark_shows_moon(actor):
    """theme='dark' 時，ThemeToggle 含月亮 path（MoonPaths SVG）。"""
    html = _build_topbar_html(actor, theme="dark")
    assert "M21 12.79" in html


def test_theme_toggle_dark_no_circle(actor):
    """theme='dark' 時，不含太陽 <circle>（圖示互斥）。"""
    html = _build_topbar_html(actor, theme="dark")
    assert "<circle" not in html


def test_theme_toggle_light_shows_sun(actor):
    """theme='light' 時，ThemeToggle 含太陽圖示（circle + 8 line）。"""
    html = _build_topbar_html(actor, theme="light")
    assert "<circle" in html and "<line" in html


def test_theme_toggle_light_no_moon(actor):
    """theme='light' 時，不含月亮 path（圖示互斥）。"""
    html = _build_topbar_html(actor, theme="light")
    assert "M21 12.79" not in html


def test_theme_toggle_aria_pressed_false_when_dark(actor):
    """dark mode：aria-pressed='false'（isLight=False，對齊 ThemeToggle.tsx aria-pressed={isLight}）。"""
    html = _build_topbar_html(actor, theme="dark")
    assert 'aria-pressed="false"' in html


def test_theme_toggle_aria_pressed_true_when_light(actor):
    """light mode：aria-pressed='true'（isLight=True）。"""
    html = _build_topbar_html(actor, theme="light")
    assert 'aria-pressed="true"' in html


def test_theme_toggle_aria_label_switch_to_light_when_dark(actor):
    """dark mode：aria-label='切換為淺色'（下一個動作是切到淺色）。"""
    html = _build_topbar_html(actor, theme="dark")
    assert 'aria-label="切換為淺色"' in html


def test_theme_toggle_aria_label_switch_to_dark_when_light(actor):
    """light mode：aria-label='切換為深色'（下一個動作是切到深色）。"""
    html = _build_topbar_html(actor, theme="light")
    assert 'aria-label="切換為深色"' in html


def test_theme_toggle_default_is_dark(actor):
    """theme 未傳時預設 dark（呼叫端無需明確傳值）。"""
    html = _build_topbar_html(actor)
    assert "M21 12.79" in html


def test_theme_toggle_has_class(actor):
    """ThemeToggle 按鈕有 ss-topbar__theme-btn class。"""
    html = _build_topbar_html(actor)
    assert "ss-topbar__theme-btn" in html


# ── 右側：登出按鈕 ────────────────────────────────────────────────────────────

def test_logout_button_present(actor):
    """登出按鈕存在（元件一致性）。"""
    html = _build_topbar_html(actor)
    assert "登出" in html


def test_logout_button_is_button_element(actor):
    """登出是 <button> 元素（不是 <a>，避免 GET 請求）。"""
    html = _build_topbar_html(actor)
    idx = html.index("登出")
    before = html[max(0, idx - 200): idx]
    assert "<button" in before


# ── 整體結構 ──────────────────────────────────────────────────────────────────

def test_topbar_root_class(actor):
    """頂層容器有 ss-topbar class。"""
    html = _build_topbar_html(actor)
    assert 'class="ss-topbar"' in html
