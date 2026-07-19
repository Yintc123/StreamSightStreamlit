from __future__ import annotations

import streamlit as st

from lib import theme
from lib.theme import build_theme_cookie_string, parse_theme


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
    """None（cookie 不存在）→ 收斂到 'dark'（預設值）。"""
    assert parse_theme(None) == "dark"


def test_parse_theme_unknown():
    """未知字串（如 'system'）→ 收斂到 'dark'。"""
    assert parse_theme("system") == "dark"


def test_parse_theme_empty():
    """空字串 → 收斂到 'dark'。"""
    assert parse_theme("") == "dark"


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
