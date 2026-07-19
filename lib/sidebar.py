"""側欄寬度 cookie 同步(規格 docs/specs/sidebar-width-sync.md)。

橋接 Streamlit 原生 localStorage['sidebarWidth'] ⇄ sidebar_width cookie,
讓 Next.js CMS 與 Streamlit 左欄共用同一寬度。
"""
from __future__ import annotations

import json

SIDEBAR_COOKIE = "sidebar_width"
SIDEBAR_MIN_WIDTH = 200
SIDEBAR_MAX_WIDTH = 600
# 僅文件化 Streamlit 原生預設值,不參與邏輯(契約不寫回修正,見規格 §2、§3.3)
SIDEBAR_DEFAULT_WIDTH = 256
SIDEBAR_COOKIE_MAX_AGE = 31_536_000  # 1 年(同 theme cookie)


# 橋接 JS(規格 §3.2):inbound cookie → localStorage + reload(guard 防迴圈);
# outbound 靠父頁 storage 事件(拖曳結束 / 雙擊重設寫 localStorage)→ 寫 cookie。
# localStorage 空(首訪)時 stored 為 NaN,與任何 fromCookie 不等 → 走 inbound
# 採 cookie 值,為期望行為(CMS 先設定、Streamlit 首訪即同寬)。
_SIDEBAR_SYNC_JS = r"""
(function () {
  var win = window.parent;
  try {
    var KEY = 'sidebarWidth', GUARD = 'ss-sidebar-sync';
    var SECURE = "__SECURE__";
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

    // inbound:cookie 有值且與 localStorage 不一致 → 覆寫 + reload(guard 防迴圈)
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

    // 建檔:cookie 缺省而本地已有合法寬度 → 以本地值建立 cookie
    if (fromCookie === null && valid(stored)) writeCookie(stored);

    // outbound:父頁寫 localStorage(拖曳結束 / 雙擊重設)→ storage 事件 → 寫 cookie
    window.addEventListener('storage', function (e) {
      if (e.key !== KEY || !e.newValue) return;
      var v = parseInt(e.newValue, 10);
      if (valid(v)) writeCookie(v);
    });
  } catch (e) {}
})();
"""


def build_sidebar_sync_js(is_prod: bool = False) -> str:
    """回傳橋接 JS("__SECURE__" 以 json.dumps 填入,同 build_theme_toggle_js 手法)。"""
    secure = "; Secure" if is_prod else ""
    return _SIDEBAR_SYNC_JS.replace('"__SECURE__"', json.dumps(secure))


def inject_sidebar_sync_js(enabled: bool = False, is_prod: bool = False) -> None:
    """enabled=False → no-op(kill-switch);True → 注入橋接 JS(height=0)。

    每次 rerun 重注入為冪等:inbound 判斷冪等;storage listener 隨舊 iframe
    銷毀,不累積(規格 §3.2)。
    """
    if not enabled:
        return
    import streamlit.components.v1 as components

    components.html(f"<script>{build_sidebar_sync_js(is_prod)}</script>", height=0)


def parse_sidebar_width(raw: "str | None") -> "int | None":
    """ASCII 十進位整數字串且在 [200, 600] → int;其餘 → None(與 JS valid() 同語義)。"""
    # isdigit 排除空字串 / 負號 / 小數點;isascii 排除上標(int 會 ValueError)與
    # 全形數字(JS 端 regex \d 僅收 ASCII,契約需同語義)
    if raw is None or not (raw.isascii() and raw.isdigit()):
        return None
    value = int(raw)
    return value if SIDEBAR_MIN_WIDTH <= value <= SIDEBAR_MAX_WIDTH else None
