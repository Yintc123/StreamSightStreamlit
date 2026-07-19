from __future__ import annotations

import streamlit as st

from lib import theme
from lib.theme import (
    build_force_light_js,
    build_theme_cookie_string,
    build_theme_toggle_js,
    parse_theme,
)


def test_load_css_injects_style_tag(monkeypatch, tmp_path):
    css = tmp_path / "x.css"
    css.write_text(".a{color:red}", encoding="utf-8")

    calls: dict = {}

    def fake_markdown(body, **kwargs):
        calls["body"] = body
        calls["kwargs"] = kwargs

    monkeypatch.setattr(st, "markdown", fake_markdown)

    theme.load_css(str(css))

    assert "<style>" in calls["body"]
    assert ".a{color:red}" in calls["body"]
    assert calls["kwargs"].get("unsafe_allow_html") is True


# ── parse_theme ───────────────────────────────────────────────────────────────

def test_parse_theme_dark():
    """'dark' 輸入 → 'dark'。"""
    assert parse_theme("dark") == "dark"


def test_parse_theme_light():
    """'light' 輸入 → 'light'。"""
    assert parse_theme("light") == "light"


def test_parse_theme_none():
    """None（cookie 不存在）→ 收斂到 'light'（應用程式預設為白天主題）。"""
    assert parse_theme(None) == "light"


def test_parse_theme_unknown():
    """未知字串（如 'system'）→ 收斂到 'light'。"""
    assert parse_theme("system") == "light"


def test_parse_theme_empty():
    """空字串 → 收斂到 'light'。"""
    assert parse_theme("") == "light"


# ── build_theme_cookie_string ─────────────────────────────────────────────────

def test_cookie_string_contains_theme_value():
    """回傳字串包含 theme=dark。"""
    assert "theme=dark" in build_theme_cookie_string("dark")


def test_cookie_string_light_contains_theme_value():
    """回傳字串包含 theme=light。"""
    assert "theme=light" in build_theme_cookie_string("light")


def test_cookie_string_has_max_age():
    """Max-Age 為 31536000（1 年，對齊 Frontend THEME_COOKIE_MAX_AGE）。"""
    assert "Max-Age=31536000" in build_theme_cookie_string("light")


def test_cookie_string_has_path():
    """Path=/ 存在。"""
    assert "Path=/" in build_theme_cookie_string("dark")


def test_cookie_string_has_samesite_lax():
    """SameSite=Lax 存在（對齊 Frontend buildThemeCookieString）。"""
    assert "SameSite=Lax" in build_theme_cookie_string("light")


def test_cookie_string_no_secure_in_dev():
    """is_prod=False 時不含 Secure 屬性。"""
    assert "Secure" not in build_theme_cookie_string("dark", is_prod=False)


def test_cookie_string_has_secure_in_prod():
    """is_prod=True 時含 Secure 屬性（對齊 Frontend isProd 條件）。"""
    assert "Secure" in build_theme_cookie_string("dark", is_prod=True)


# ── 強制白天模式（config.toml base）──────────────────────────────────────────

def test_config_toml_forces_light_base():
    """[theme] 需明確 base = "light"。

    未設定 base 時，Streamlit 底層元件（選單 / dialog / dataframe 等）會跟隨
    瀏覽器 prefers-color-scheme，深色系統偏好下整站變暗——本應用只支援白天模式。
    """
    from pathlib import Path

    config = (Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml").read_text(
        encoding="utf-8"
    )
    assert 'base = "light"' in config


def test_config_toml_uses_frontend_font_stack():
    """[theme] font 需對齊 Frontend globals.css --font-sans。

    Frontend: "PingFang TC", "Noto Sans TC", system-ui, sans-serif。
    Streamlit ≥1.46 的 theme.font 支援逗號分隔自訂字體 stack，
    能用 config.toml 解決就不寫 CSS（design-system 原則）。
    """
    from pathlib import Path

    config = (Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml").read_text(
        encoding="utf-8"
    )
    assert "PingFang TC" in config
    assert "Noto Sans TC" in config


# ── 強制白天模式（清除瀏覽器記住的 Appearance 覆寫）──────────────────────────
#
# config.toml 的 base="light" 只是「乾淨瀏覽器」的預設；Streamlit 允許使用者
# 在 ☰ → Settings → Appearance 改主題，選擇存於 localStorage（key 前綴
# stActiveTheme），且會「優先於 config」。深色系統偏好或使用者曾切過 dark，
# 就會蓋掉 light 造成整站變黑（頂列因寫死白色而不受影響 → 上白下黑）。
# 本 JS 在 client 端清掉非 Light 的儲存選擇並重載一次，把主題鎖回白天。


def test_force_light_js_targets_streamlit_theme_storage():
    """鎖定 Streamlit 存放主題選擇的 localStorage key（前綴 stActiveTheme）。"""
    assert "stActiveTheme" in build_force_light_js()


def test_force_light_js_clears_non_light_choice():
    """需清除（removeItem）已儲存的非 Light 主題，讓 Streamlit 落回 config。"""
    assert "removeItem" in build_force_light_js()


def test_force_light_js_reloads_to_apply():
    """清除後需重載一次，讓 Streamlit 以 config（light）重新渲染。"""
    assert "reload" in build_force_light_js()


def test_force_light_js_guards_against_reload_loop():
    """以 sessionStorage 旗標防止無限重載。"""
    assert "sessionStorage" in build_force_light_js()


# ── 主題切換 JS（啟用態，theme-toggle.md §6.2.3）─────────────────────────────
#
# ThemeToggle 啟用時的 client-side 切換腳本。JS 為字串常數，比照 _FORCE_LIGHT_JS
# 以「子字串斷言」驗證關鍵操作存在；端到端點擊行為（DOM/cookie 真的變）另以
# 瀏覽器煙霧測試涵蓋（非 pytest 範圍）。


def test_toggle_js_reads_theme_cookie():
    """讀 parent document 的 theme cookie。"""
    js = build_theme_toggle_js()
    assert "pdoc.cookie" in js
    assert "match(" in js


def test_toggle_js_converges_unknown_to_light():
    """未知 / 缺省 cookie 收斂到 'light'（決策 D1-a）。"""
    assert "m ? m[1] : 'light'" in build_theme_toggle_js()


def test_toggle_js_registers_click_listener():
    """對切換按鈕註冊 click 監聽器。"""
    js = build_theme_toggle_js()
    assert "addEventListener" in js
    assert "'click'" in js


def test_toggle_js_guards_duplicate_binding():
    """以 per-element dataset 旗標防止重複綁定（Streamlit rerun 產生新按鈕）。"""
    assert "ssThemeBound" in build_theme_toggle_js()


def test_toggle_js_cookie_has_max_age():
    """切換寫 cookie 帶 Max-Age=31536000（對齊 Frontend）。"""
    assert "Max-Age=31536000" in build_theme_toggle_js()


def test_toggle_js_no_secure_in_dev():
    """is_prod=False → cookie 不含 Secure。"""
    assert "Secure" not in build_theme_toggle_js(is_prod=False)


def test_toggle_js_has_secure_in_prod():
    """is_prod=True → cookie 含 Secure。"""
    assert "Secure" in build_theme_toggle_js(is_prod=True)


def test_toggle_js_swaps_sun_and_moon_icons():
    """syncButton 依主題換太陽 / 月亮 SVG。"""
    js = build_theme_toggle_js()
    assert "circle cx=" in js          # 太陽（json.dumps 後引號被轉義）
    assert "M21 12.79A9" in js         # 月亮 path


# ── inject_theme_js 分支（依 enable_theme_toggle）──────────────────────────────


def _capture_injected_html(monkeypatch, **kwargs) -> str:
    import streamlit.components.v1 as components

    captured: dict = {}
    monkeypatch.setattr(components, "html", lambda body, **kw: captured.setdefault("body", body))
    theme.inject_theme_js(**kwargs)
    return captured["body"]


def test_inject_theme_js_enabled_injects_click_listener(monkeypatch):
    """enable_theme_toggle=True → 注入含 click 監聽的切換 JS。"""
    assert "addEventListener" in _capture_injected_html(monkeypatch, enable_theme_toggle=True)


def test_inject_theme_js_disabled_has_no_click_listener(monkeypatch):
    """enable_theme_toggle=False → 仍是固定 light 的 _THEME_JS，無 click 監聽。"""
    assert "addEventListener" not in _capture_injected_html(monkeypatch, enable_theme_toggle=False)


def test_inject_theme_js_always_includes_force_light(monkeypatch):
    """兩種模式都保留 _FORCE_LIGHT_JS（鎖 Streamlit 內建元件為 light）。"""
    assert "stActiveTheme" in _capture_injected_html(monkeypatch, enable_theme_toggle=True)
    assert "stActiveTheme" in _capture_injected_html(monkeypatch, enable_theme_toggle=False)


# ── 側欄收合 / 展開按鈕 icon 顏色（main.css）───────────────────────────────────
# Streamlit 1.50 對按鈕內的 DynamicIcon 傳入 color=fadedText60，顏色直接設在
# icon span（stIconMaterial）本身；只設在 button 的顏色無法靠繼承生效，
# 深色底下 icon 會維持深灰而看不見。故 light / dark 都需直接覆寫 span。


def _read_main_css() -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parents[2] / "styles" / "main.css").read_text(
        encoding="utf-8"
    )


def test_css_sets_collapse_icon_color_on_icon_span():
    """light：收合按鈕 icon span 需直接設 ink-AA（對齊 CmsSideNav text-ink-AA）。"""
    import re

    m = re.search(
        r'^\[data-testid="stSidebarCollapseButton"\] \[data-testid="stIconMaterial"\]'
        r"[^{]*\{[^}]*color:\s*rgba\(15, 23, 42, 0\.66\)",
        _read_main_css(),
        re.MULTILINE,
    )
    assert m, "main.css 缺少 light 模式收合按鈕 stIconMaterial 顏色覆寫"


def test_dark_css_sets_collapse_icon_color_on_icon_span():
    """dark：收合按鈕 icon span 需直接設深色 ink-AA，否則深色底看不到。"""
    import re

    m = re.search(
        r'html\[data-theme="dark"\] \[data-testid="stSidebarCollapseButton"\] '
        r'\[data-testid="stIconMaterial"\][^{]*\{[^}]*color:\s*rgba\(230, 237, 246, 0\.72\)',
        _read_main_css(),
    )
    assert m, "main.css 缺少 dark 模式收合按鈕 stIconMaterial 顏色覆寫"


def test_css_sets_expand_icon_color_on_icon_span():
    """light：展開按鈕（stExpandSidebarButton）icon span 需直接設 ink-AA。"""
    import re

    m = re.search(
        r'^\[data-testid="stExpandSidebarButton"\] \[data-testid="stIconMaterial"\]'
        r"[^{]*\{[^}]*color:\s*rgba\(15, 23, 42, 0\.66\)",
        _read_main_css(),
        re.MULTILINE,
    )
    assert m, "main.css 缺少 light 模式展開按鈕 stIconMaterial 顏色覆寫"


def test_dark_css_sets_expand_icon_color_on_icon_span():
    """dark：展開按鈕 icon span 需直接設深色 ink-AA。"""
    import re

    m = re.search(
        r'html\[data-theme="dark"\] \[data-testid="stExpandSidebarButton"\] '
        r'\[data-testid="stIconMaterial"\][^{]*\{[^}]*color:\s*rgba\(230, 237, 246, 0\.72\)',
        _read_main_css(),
    )
    assert m, "main.css 缺少 dark 模式展開按鈕 stIconMaterial 顏色覆寫"
