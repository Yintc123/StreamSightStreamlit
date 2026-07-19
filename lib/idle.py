"""閒置逾時（Idle Timeout）：純前端 JS 偵測滑鼠/鍵盤閒置。

見規格 docs/specs/idle-timeout.md。純邏輯（產生計時器 JS、解析登出原因）放此處，
app.py 只負責注入與路由；不做伺服器端兜底（D2）。
"""
from __future__ import annotations

from typing import Optional

from lib.config import get_settings

# 登出原因白名單（§5.2）：來自 query param、僅供顯示、不參與安全判斷。
_ALLOWED_LOGOUT_REASONS = frozenset({"idle"})


def parse_logout_reason(raw: Optional[str]) -> Optional[str]:
    """收斂 query param 的 reason 到白名單；非白名單一律回 None，避免反射式注入。"""
    return raw if raw in _ALLOWED_LOGOUT_REASONS else None


# 計時器 JS 模板（§4.3）：跑在 components.html 的 iframe 內，操作 window.parent。
# 以 token 取代注入數值（JS 大量大括號，避免 str.format/f-string 衝突）。
_IDLE_JS_TEMPLATE = r"""
(function () {
  var W = window.parent, D = W.document;
  var TIMEOUT_MS = __TIMEOUT_MS__, THROTTLE_MS = __THROTTLE_MS__;
  var KEY = 'ss_last_activity';
  if (W.__ssIdleCleanup) { W.__ssIdleCleanup(); }        // 冪等：清上一輪

  var timer = null, last = 0;
  var events = ['mousemove', 'mousedown', 'wheel', 'keydown'];  // 僅滑鼠 / 鍵盤

  function fireLogout() { W.location.href = '?logout=1&reason=idle'; }
  function schedule() { if (timer) W.clearTimeout(timer); timer = W.setTimeout(fireLogout, TIMEOUT_MS); }
  function onActivity() {
    var now = Date.now();
    if (now - last < THROTTLE_MS) return;                // 節流
    last = now;
    try { W.localStorage.setItem(KEY, String(now)); } catch (e) {}
    schedule();
  }
  function onStorage(e) { if (e.key === KEY) schedule(); }  // 跨分頁：他頁有活動 → 重置

  events.forEach(function (ev) { D.addEventListener(ev, onActivity, { passive: true }); });
  W.addEventListener('storage', onStorage);
  schedule();

  W.__ssIdleCleanup = function () {
    if (timer) W.clearTimeout(timer);
    events.forEach(function (ev) { D.removeEventListener(ev, onActivity, { passive: true }); });
    W.removeEventListener('storage', onStorage);
    W.__ssIdleCleanup = null;
  };
})();
"""


def build_idle_js(timeout_seconds: int, throttle_seconds: int) -> str:
    """產生閒置計時器 JS（純函式）；秒 → 毫秒後填入模板。"""
    return (
        _IDLE_JS_TEMPLATE
        .replace("__TIMEOUT_MS__", str(timeout_seconds * 1000))
        .replace("__THROTTLE_MS__", str(throttle_seconds * 1000))
    )


def inject_idle_js() -> None:
    """每次 rerun 注入冪等閒置計時器 JS（純 client-side，不觸發 Python rerun）。

    對齊 theme.inject_theme_js：以 components.html 於 iframe 內注入，操作 window.parent。
    """
    import streamlit.components.v1 as components

    settings = get_settings()
    js = build_idle_js(
        settings.idle_timeout_seconds,
        settings.idle_activity_throttle_seconds,
    )
    components.html(f"<script>{js}</script>", height=0)
