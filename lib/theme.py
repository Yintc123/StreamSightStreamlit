"""樣式載入與主題切換。

見規格 docs/specs/design-system.md 與 docs/specs/theme-toggle.md。
主題優先(config.toml),CSS 最小化；ThemeToggle 以純 client-side JS 實作。
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

THEME_COOKIE = "theme"
THEME_COOKIE_MAX_AGE = 31_536_000  # 1 year（對齊 Frontend schema.ts）

# JS 字串常數（模組層，避免 inject 時重複建構）
# 對齊規格書 docs/specs/theme-toggle.md §5.2
_THEME_JS = r"""
(function () {
  var COOKIE = 'theme';
  var MAX_AGE = 31536000;
  var par = window.parent;
  var pdoc = par.document;

  var SUN_INNER = [
    '<circle cx="12" cy="12" r="5"/>',
    '<line x1="12" y1="1" x2="12" y2="3"/>',
    '<line x1="12" y1="21" x2="12" y2="23"/>',
    '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>',
    '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>',
    '<line x1="1" y1="12" x2="3" y2="12"/>',
    '<line x1="21" y1="12" x2="23" y2="12"/>',
    '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>',
    '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'
  ].join('');
  var MOON_INNER = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';

  function readCookie() {
    var m = pdoc.cookie.match(/(?:^|;\s*)theme=([^;]+)/);
    return m && (m[1] === 'light' || m[1] === 'dark') ? m[1] : 'dark';
  }

  function applyTheme(t) {
    pdoc.documentElement.dataset.theme = t;
    pdoc.cookie = COOKIE + '=' + t + '; Max-Age=' + MAX_AGE + '; Path=/; SameSite=Lax';
  }

  function enableTransition() {
    pdoc.documentElement.setAttribute('data-theme-ready', '');
  }

  function syncButton(t) {
    var btn = pdoc.querySelector('.ss-topbar__theme-btn');
    if (!btn) return;
    var isLight = t === 'light';
    btn.setAttribute('aria-pressed', String(isLight));
    btn.setAttribute('aria-label', isLight ? '切換為深色' : '切換為淺色');
    var svg = btn.querySelector('svg');
    if (svg) svg.innerHTML = isLight ? SUN_INNER : MOON_INNER;
  }

  var initial = readCookie();
  applyTheme(initial);
  syncButton(initial);
  enableTransition();

  if (!par.__ssThemeReady) {
    par.__ssThemeReady = true;
    pdoc.addEventListener('click', function (e) {
      var btn = e.target.closest('.ss-topbar__theme-btn');
      if (!btn) return;
      var current = pdoc.documentElement.dataset.theme || 'dark';
      var next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      syncButton(next);
    });
  }
})();
"""


def load_css(path: str = "styles/main.css") -> None:
    """讀取外部 CSS 並以 <style> 注入;每次 rerun 重注入無副作用。"""
    css = Path(path).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def parse_theme(raw: "str | None") -> str:
    """未知 / 缺省值收斂到 'dark'（對齊 Frontend parseTheme）。"""
    return raw if raw in ("light", "dark") else "dark"


def build_theme_cookie_string(theme: str, is_prod: bool = False) -> str:
    """組裝 cookie 字串（純函式，對齊 Frontend buildThemeCookieString）。"""
    secure = "; Secure" if is_prod else ""
    return f"{THEME_COOKIE}={theme}; Max-Age={THEME_COOKIE_MAX_AGE}; Path=/; SameSite=Lax{secure}"


def init_theme_state() -> None:
    """session_state['theme'] 初始化（首次 session 設預設值 'dark'）。"""
    if "theme" not in st.session_state:
        st.session_state["theme"] = "dark"


def inject_theme_js() -> None:
    """每次 rerun 注入冪等 ThemeToggle JS（純 client-side 切換，不觸發 Python rerun）。"""
    import streamlit.components.v1 as components
    components.html(f"<script>{_THEME_JS}</script>", height=0)
