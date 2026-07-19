"""lib/sidebar.py 單元測試(規格 docs/specs/sidebar-width-sync.md §4)。"""
import pytest

from lib import sidebar
from lib.sidebar import build_sidebar_sync_js, parse_sidebar_width


# ── parse_sidebar_width:十進位整數字串且在 [200, 600] → int;其餘 → None ─────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("320", 320),   # happy
        ("200", 200),   # 下界(含)
        ("600", 600),   # 上界(含)
    ],
)
def test_parse_sidebar_width_happy(raw, expected):
    """合法整數字串且在值域內 → int。"""
    assert parse_sidebar_width(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [None, "", "abc", "199", "601", "320.5"],
)
def test_parse_sidebar_width_edge_returns_none(raw):
    """缺省 / 非數字 / 越界 / 浮點 → None(與 JS valid() 同語義)。"""
    assert parse_sidebar_width(raw) is None


@pytest.mark.parametrize(
    "raw",
    ["²⁰⁰", "３２０"],  # 上標數字(int() 會 ValueError)/ 全形數字(JS \d 不收)
)
def test_parse_sidebar_width_non_ascii_digits_return_none(raw):
    """非 ASCII 數字 → None 且不丟例外(JS 端 regex \\d 僅收 ASCII,契約同語義)。"""
    assert parse_sidebar_width(raw) is None


# ── build_sidebar_sync_js:"__SECURE__" 以 json.dumps 填入(同 theme JS 手法)──


def test_sync_js_dev_bridges_cookie_and_localstorage():
    """dev:含 cookie 名、Streamlit localStorage key 與 Max-Age;不含 Secure。"""
    js = build_sidebar_sync_js()
    assert "sidebar_width" in js       # cookie 名(契約 §2)
    assert "sidebarWidth" in js        # Streamlit 原生 localStorage key
    assert "Max-Age=31536000" in js    # 1 年
    assert "Secure" not in js


def test_sync_js_prod_appends_secure():
    """prod:含 '; Secure'(json.dumps 注入,無佔位符與引號洩漏)。"""
    js = build_sidebar_sync_js(is_prod=True)
    assert "; Secure" in js
    assert "__SECURE__" not in js      # 佔位符已被替換
    assert '""; Secure""' not in js    # 引號未洩漏


# ── inject_sidebar_sync_js:kill-switch(沿用 test_theme _capture 手法)─────────


def _capture_html_calls(monkeypatch) -> list:
    import streamlit.components.v1 as components

    calls: list = []
    monkeypatch.setattr(
        components, "html", lambda body, **kw: calls.append((body, kw))
    )
    return calls


def test_inject_disabled_is_noop(monkeypatch):
    """enabled=False → 不呼叫 components.html(kill-switch)。"""
    calls = _capture_html_calls(monkeypatch)
    sidebar.inject_sidebar_sync_js(enabled=False)
    assert calls == []


def test_inject_enabled_injects_once_height_zero(monkeypatch):
    """enabled=True → 注入一次 <script>、height=0,內容為橋接 JS。"""
    calls = _capture_html_calls(monkeypatch)
    sidebar.inject_sidebar_sync_js(enabled=True)
    assert len(calls) == 1
    body, kwargs = calls[0]
    assert "sidebarWidth" in body
    assert kwargs.get("height") == 0


def test_inject_enabled_prod_passes_secure(monkeypatch):
    """is_prod=True 透傳 build_sidebar_sync_js → 注入內容含 Secure。"""
    calls = _capture_html_calls(monkeypatch)
    sidebar.inject_sidebar_sync_js(enabled=True, is_prod=True)
    assert "; Secure" in calls[0][0]
