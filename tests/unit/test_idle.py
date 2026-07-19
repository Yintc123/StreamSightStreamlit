"""lib/idle.py 單元測試（idle-timeout §8.1）。

純函式：parse_logout_reason（白名單）、build_idle_js（計時器 JS 產生）。
"""
from __future__ import annotations

import pytest

from lib import idle


# --- parse_logout_reason：白名單（§5.2） ---

def test_parse_reason_idle_passes():
    assert idle.parse_logout_reason("idle") == "idle"


@pytest.mark.parametrize("raw", [None, "", "bogus", "<script>alert(1)</script>", "IDLE", "idle "])
def test_parse_reason_rejects_non_whitelisted(raw):
    """未知值 / None / 空字串 / 注入字串 / 大小寫不符 → None（只認精確 'idle'）。"""
    assert idle.parse_logout_reason(raw) is None


# --- build_idle_js：計時器 JS 產生（§4.2、§4.3、§8.1） ---

def test_build_idle_js_converts_seconds_to_ms():
    """timeout/throttle 秒 → 毫秒（JS 用 ms）。"""
    js = idle.build_idle_js(timeout_seconds=900, throttle_seconds=30)
    assert "900000" in js   # 900 * 1000
    assert "30000" in js    # 30 * 1000


def test_build_idle_js_redirects_to_logout_idle():
    """到點導向 ?logout=1&reason=idle（登出訊號）。"""
    js = idle.build_idle_js(900, 30)
    assert "?logout=1&reason=idle" in js


def test_build_idle_js_listens_mouse_and_keyboard_only():
    """僅監聽滑鼠/鍵盤事件；不含 touchstart（依 D2 只偵測滑鼠/鍵盤）。"""
    js = idle.build_idle_js(900, 30)
    for ev in ("mousemove", "mousedown", "wheel", "keydown"):
        assert ev in js
    assert "touchstart" not in js


def test_build_idle_js_is_idempotent_cleanup():
    """具冪等清理鉤子，避免每次 rerun 重注入時堆疊監聽/計時器。"""
    js = idle.build_idle_js(900, 30)
    assert "__ssIdleCleanup" in js


def test_build_idle_js_cross_tab_sync():
    """跨分頁同步：寫 localStorage 並監聽 storage 事件。"""
    js = idle.build_idle_js(900, 30)
    assert "localStorage" in js
    assert "storage" in js


def test_build_idle_js_operates_on_parent_document():
    """元件在 iframe 內，需操作 window.parent（對齊 theme.inject_theme_js）。"""
    js = idle.build_idle_js(900, 30)
    assert "window.parent" in js


# --- inject_idle_js：Streamlit 接縫（§7 模組表；對齊 theme.inject_theme_js） ---

def test_inject_idle_js_emits_script_with_configured_timeout(monkeypatch):
    """讀 settings 的 idle 門檻，以 components.html 注入 <script>（height=0）。"""
    import streamlit.components.v1 as components

    captured = {}

    def _fake_html(html, **kwargs):
        captured["html"] = html
        captured["kwargs"] = kwargs

    monkeypatch.setattr(components, "html", _fake_html)
    monkeypatch.setenv("IDLE_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("IDLE_ACTIVITY_THROTTLE_SECONDS", "5")
    from lib.config import get_settings
    get_settings.cache_clear()

    idle.inject_idle_js()

    assert "<script>" in captured["html"]
    assert "10000" in captured["html"]        # 10s → ms
    assert "?logout=1&reason=idle" in captured["html"]
    assert captured["kwargs"].get("height") == 0
