"""閒置逾時（Idle Timeout）：純前端 JS 偵測滑鼠/鍵盤閒置。

見規格 docs/specs/idle-timeout.md。純邏輯（產生計時器 JS、解析登出原因）放此處，
app.py 只負責注入與路由；不做伺服器端兜底（D2）。
"""
from __future__ import annotations

import json
from typing import Optional

from lib.config import get_settings

# 登出原因白名單（§5.2）：來自 query param、僅供顯示、不參與安全判斷。
_ALLOWED_LOGOUT_REASONS = frozenset({"idle"})


def parse_logout_reason(raw: Optional[str]) -> Optional[str]:
    """收斂 query param 的 reason 到白名單；非白名單一律回 None，避免反射式注入。"""
    return raw if raw in _ALLOWED_LOGOUT_REASONS else None


# 頂層框架邏輯（§4.1）：**必須在 top frame context 執行**。
# 原因：components.html 的 iframe sandbox 缺 `allow-top-navigation`，在 iframe 內
# `window.parent.location=...` 導向頂層框架會被瀏覽器靜默封鎖（手動驗證發現）。
# 故把計時器/監聽/導向都放到 parent document 的 <script> 中，`window` 即為 top。
# 以 token 取代注入數值（JS 大量大括號，避免 str.format/f-string 衝突）。
_IDLE_TOP_LOGIC = r"""
(function () {
  var TIMEOUT_MS = __TIMEOUT_MS__, THROTTLE_MS = __THROTTLE_MS__;
  var KEY = 'ss_last_activity';
  if (window.__ssIdleCleanup) { window.__ssIdleCleanup(); }  // 冪等：清上一輪

  var timer = null, last = 0;
  var events = ['mousemove', 'mousedown', 'wheel', 'keydown'];  // 僅滑鼠 / 鍵盤

  function fireLogout() { window.location.href = '?logout=1&reason=idle'; }  // top context → 導向可行
  function schedule() { if (timer) clearTimeout(timer); timer = setTimeout(fireLogout, TIMEOUT_MS); }
  function onActivity() {
    var now = Date.now();
    if (now - last < THROTTLE_MS) return;                // 節流
    last = now;
    try { localStorage.setItem(KEY, String(now)); } catch (e) {}
    schedule();
  }
  function onStorage(e) { if (e.key === KEY) schedule(); }  // 跨分頁：他頁有活動 → 重置

  events.forEach(function (ev) { document.addEventListener(ev, onActivity, { passive: true }); });
  window.addEventListener('storage', onStorage);
  schedule();

  window.__ssIdleCleanup = function () {
    if (timer) clearTimeout(timer);
    events.forEach(function (ev) { document.removeEventListener(ev, onActivity, { passive: true }); });
    window.removeEventListener('storage', onStorage);
    var el = document.getElementById('ss-idle-script');
    if (el) { el.parentNode.removeChild(el); }
    window.__ssIdleCleanup = null;
  };
})();
"""

# Bootstrap（§4.1）：跑在 components.html 的 iframe 內；靠 allow-same-origin 存取 parent DOM，
# 把上面的頂層邏輯以 <script> 掛到 parent document → 在 top frame context 執行。
_IDLE_BOOTSTRAP_TEMPLATE = r"""
(function () {
  var P = window.parent, D = P.document;
  if (P.__ssIdleCleanup) { P.__ssIdleCleanup(); }        // 清上一輪（含移除舊 script 節點）
  var s = D.createElement('script');
  s.id = 'ss-idle-script';
  s.textContent = __TOP_LOGIC_JSON__;
  D.head.appendChild(s);                                 // 掛上即在 top context 執行
})();
"""


def build_idle_js(timeout_seconds: int, throttle_seconds: int) -> str:
    """產生閒置計時器 JS（純函式）。

    回傳的是 iframe bootstrap：它把頂層邏輯注入 parent document 執行，
    以繞過 component iframe sandbox 對頂層導向的封鎖。秒 → 毫秒後填入。
    """
    top_logic = (
        _IDLE_TOP_LOGIC
        .replace("__TIMEOUT_MS__", str(timeout_seconds * 1000))
        .replace("__THROTTLE_MS__", str(throttle_seconds * 1000))
    )
    # json.dumps → 安全的 JS 字串字面值（處理引號/換行跳脫）
    return _IDLE_BOOTSTRAP_TEMPLATE.replace("__TOP_LOGIC_JSON__", json.dumps(top_logic))


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
