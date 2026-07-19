"""樣式載入與主題切換。

見規格 docs/specs/design-system.md 與 docs/specs/theme-toggle.md。
主題優先(config.toml),CSS 最小化；ThemeToggle 以純 client-side JS 實作。
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from lib.topbar import _MOON_SVG, _SUN_SVG

THEME_COOKIE = "theme"
THEME_COOKIE_MAX_AGE = 31_536_000  # 1 year（對齊 Frontend schema.ts）

# JS 字串常數（模組層，避免 inject 時重複建構）
# 對齊規格書 docs/specs/theme-toggle.md §5.2
_THEME_JS = r"""
(function () {
  var pdoc = window.parent.document;
  pdoc.documentElement.dataset.theme = 'light';
  pdoc.documentElement.setAttribute('data-theme-ready', '');
})();
"""

# Streamlit 把使用者在 ☰ → Settings → Appearance 選的主題存在 localStorage
# （key 前綴 stActiveTheme-<basePath>-vN），且會「優先於 config.toml」。深色系統
# 偏好或曾切過 dark，都會蓋掉 base="light" 讓整站變黑。以下 JS 清掉任何非 Light
# 的儲存選擇，讓 Streamlit 落回 config（白天）；sessionStorage 旗標確保一個分頁
# 生命週期內只重載一次，避免無限重載。
_FORCE_LIGHT_JS = r"""
(function () {
  var win = window.parent;
  try {
    var GUARD = 'ss-force-light';
    if (win.sessionStorage.getItem(GUARD)) return;
    win.sessionStorage.setItem(GUARD, '1');
    var cleared = false;
    Object.keys(win.localStorage).forEach(function (k) {
      if (k.indexOf('stActiveTheme') !== 0) return;
      var v = win.localStorage.getItem(k) || '';
      if (v.indexOf('"Light"') === -1) {   // 儲存的不是內建 Light → 清掉落回 config
        win.localStorage.removeItem(k);
        cleared = true;
      }
    });
    if (cleared) win.location.reload();
  } catch (e) {}
})();
"""


# 啟用切換功能（ENABLE_THEME_TOGGLE=1）時注入的 client-side 切換腳本。
# 純 client-side：讀 cookie → 設 data-theme → 寫 cookie → 換 icon/aria，全程不 rerun
# （theme-toggle.md §6.2.3）。__SUN__/__MOON__/"__SECURE__" 由 build_theme_toggle_js
# 以 json.dumps 安全填入。per-element dataset 旗標防重複綁定（每次 rerun 皆新按鈕）。
_THEME_TOGGLE_JS = r"""
(function () {
  var pdoc = window.parent.document;
  var SUN = __SUN__, MOON = __MOON__;
  var SECURE = "__SECURE__";
  function readTheme() {
    var m = pdoc.cookie.match(/(?:^|;\s*)theme=(light|dark)(?:;|$)/);
    return m ? m[1] : 'light';
  }
  function applyTheme(t) {
    pdoc.documentElement.dataset.theme = t;
    pdoc.cookie = 'theme=' + t + '; Max-Age=31536000; Path=/; SameSite=Lax' + SECURE;
  }
  function syncButton(btn, t) {
    var isLight = t === 'light';
    btn.setAttribute('aria-pressed', isLight ? 'true' : 'false');
    btn.setAttribute('aria-label', isLight ? '切換為深色' : '切換為淺色');
    btn.innerHTML = isLight ? SUN : MOON;
  }
  var current = readTheme();
  applyTheme(current);
  pdoc.documentElement.setAttribute('data-theme-ready', '');
  var tries = 0;
  (function bind() {
    var btn = pdoc.querySelector('.ss-topbar__theme-btn');
    if (!btn) { if (tries++ < 10) requestAnimationFrame(bind); return; }
    syncButton(btn, pdoc.documentElement.dataset.theme || current);
    if (!btn.dataset.ssThemeBound) {
      btn.dataset.ssThemeBound = '1';
      btn.addEventListener('click', function () {
        var next = (pdoc.documentElement.dataset.theme === 'dark') ? 'light' : 'dark';
        applyTheme(next);
        syncButton(pdoc.querySelector('.ss-topbar__theme-btn'), next);
      });
    }
  })();
})();
"""


def build_force_light_js() -> str:
    """回傳強制白天模式的 client-side JS（清除 Streamlit 記住的深色 Appearance）。"""
    return _FORCE_LIGHT_JS


def build_theme_toggle_js(is_prod: bool = False) -> str:
    """回傳啟用態的 ThemeToggle 切換 JS（SVG 與 Secure 片段以 json.dumps 安全填入）。"""
    secure = "; Secure" if is_prod else ""
    return (
        _THEME_TOGGLE_JS.replace("__SUN__", json.dumps(_SUN_SVG))
        .replace("__MOON__", json.dumps(_MOON_SVG))
        .replace('"__SECURE__"', json.dumps(secure))
    )


def load_css(path: str = "styles/main.css") -> None:
    """讀取外部 CSS 並以 <style> 注入;每次 rerun 重注入無副作用。"""
    css = Path(path).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def parse_theme(raw: "str | None") -> str:
    """未知 / 缺省值收斂到 'light'（應用程式預設白天主題）。"""
    return raw if raw in ("light", "dark") else "light"


def build_theme_cookie_string(theme: str, is_prod: bool = False) -> str:
    """組裝 cookie 字串（純函式，對齊 Frontend buildThemeCookieString）。"""
    secure = "; Secure" if is_prod else ""
    return f"{THEME_COOKIE}={theme}; Max-Age={THEME_COOKIE_MAX_AGE}; Path=/; SameSite=Lax{secure}"


def init_theme_state() -> None:
    """session_state['theme'] 初始化（首次 session 設預設值 'light'）。"""
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"


def inject_theme_js(enable_theme_toggle: bool = False, is_prod: bool = False) -> None:
    """每次 rerun 注入冪等 ThemeToggle JS（純 client-side，不觸發 Python rerun）。

    enable_theme_toggle=True → 注入可切換的 _THEME_TOGGLE_JS；False → 固定 light 的
    _THEME_JS。兩者皆前置 _FORCE_LIGHT_JS，鎖 Streamlit 內建元件恆 light（§11）。
    """
    import streamlit.components.v1 as components

    theme_js = build_theme_toggle_js(is_prod) if enable_theme_toggle else _THEME_JS
    components.html(f"<script>{_FORCE_LIGHT_JS}{theme_js}</script>", height=0)
