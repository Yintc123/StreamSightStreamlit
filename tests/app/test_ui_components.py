"""tests/app/test_ui_components.py — lib/ui.py UI 元件 AppTest 頁面行為測試。"""
from __future__ import annotations

from streamlit.testing.v1 import AppTest

from lib.ui import Metric


def _iter_blocks(node):
    """遞迴走訪 AppTest element tree 的所有子節點（供檢查容器 proto.id）。"""
    kids = node.children
    if isinstance(kids, dict):
        kids = list(kids.values())
    for c in (kids or []):
        yield c
        if hasattr(c, "children"):
            yield from _iter_blocks(c)


def _block_ids(at):
    """回傳 element tree 中所有帶 proto.id 的容器 id 清單。"""
    return [
        getattr(getattr(b, "proto", None), "id", "") or ""
        for b in _iter_blocks(at.main)
    ]


# ---------------------------------------------------------------------------
# page_shell：每頁最外層穩定容器（防跨頁殘影 / ghosting）
#
# 殘影根因：Streamlit 前端對 element tree 做「位置 + 型別」的增量 diff，
# 切頁時同位置、同型別的舊 element 會被就地重用/暫留，直到整輪跑完才修剪。
# 修法：每頁最外層包一個帶「頁面專屬 key」的容器，讓該區塊有穩定且唯一的
# element 身分（proto.id 編入 page-<name>）；切頁時 key 不同 → 整塊 remount
# 取代而非同位置重用，藉此消除殘影。見 docs/specs/ui.md、app-skeleton.md。
# ---------------------------------------------------------------------------

def test_page_shell_gives_page_scoped_container_identity():
    """page_shell(name) 產生的容器 element id 應編入 page-<name>，內容嵌於其中。"""
    at = AppTest.from_string(
        "import streamlit as st\n"
        "from lib.ui import page_shell\n"
        "with page_shell('analytics'):\n"
        "    st.title('資料分析')\n"
    ).run()
    assert not at.exception
    assert any(i.endswith("page-analytics") for i in _block_ids(at))
    assert at.title[0].value == "資料分析"  # 內容確實渲染在容器內


def test_page_shell_distinct_pages_get_distinct_identities():
    """不同頁名 → 不同容器 id（同位置卻不同身分＝殘影根因的反例）。"""
    def _page_id(name):
        at = AppTest.from_string(
            "import streamlit as st\n"
            "from lib.ui import page_shell\n"
            f"with page_shell({name!r}):\n"
            "    st.title('x')\n"
        ).run()
        return next(i for i in _block_ids(at) if i.endswith(f"page-{name}"))

    assert _page_id("analytics") != _page_id("data_management")


# ---------------------------------------------------------------------------
# Phase 3: empty_state (#7)
# ---------------------------------------------------------------------------

def test_empty_state_renders_info():
    at = AppTest.from_string(
        "from lib.ui import empty_state\nempty_state('查無資料')"
    ).run()
    assert not at.exception
    assert len(at.info) == 1
    assert at.info[0].value == "查無資料"


# ---------------------------------------------------------------------------
# Phase 4: metric_cards (#8, #9)
# ---------------------------------------------------------------------------

def test_metric_cards_empty_list_silent():
    at = AppTest.from_string(
        "from lib.ui import metric_cards\nmetric_cards([])"
    ).run()
    assert not at.exception
    assert len(at.metric) == 0


def test_metric_cards_renders_metric():
    at = AppTest.from_string(
        "from lib.ui import metric_cards, Metric\nmetric_cards([Metric('總計', 10)])"
    ).run()
    assert not at.exception
    assert len(at.metric) == 1
    assert at.metric[0].label == "總計"


# ---------------------------------------------------------------------------
# Phase 5: pagination_controls (#10, #11, #12)
# ---------------------------------------------------------------------------

_PAGINATION_SCRIPT = """\
import streamlit as st
from lib.ui import pagination_controls
pagination_controls(total={total}, size=20, key_prefix="t")
"""


def test_pagination_controls_total_zero_silent():
    at = AppTest.from_string(_PAGINATION_SCRIPT.format(total=0)).run()
    assert not at.exception
    assert len(at.button) == 0


def test_pagination_controls_first_page_prev_disabled():
    at = AppTest.from_string(_PAGINATION_SCRIPT.format(total=47)).run()
    assert not at.exception
    prev_btn = next(b for b in at.button if "上一頁" in b.label)
    assert prev_btn.disabled


def test_pagination_controls_last_page_next_disabled():
    at = AppTest.from_string(_PAGINATION_SCRIPT.format(total=47))
    at.session_state["t_page"] = 3  # ceil(47/20) == 3，末頁
    at.run()
    assert not at.exception
    next_btn = next(b for b in at.button if "下一頁" in b.label)
    assert next_btn.disabled


# ---------------------------------------------------------------------------
# Phase 6: filter_bar (#13–#17)
# ---------------------------------------------------------------------------

_FILTER_BAR_SCRIPT = """\
import streamlit as st
from lib.ui import filter_bar
filter_bar({categories}, key_prefix="{prefix}"{extra})
"""


def test_filter_bar_initial_render_has_selectbox_and_text_input():
    script = _FILTER_BAR_SCRIPT.format(
        categories='["全部", "感測器"]', prefix="t", extra=""
    )
    at = AppTest.from_string(script).run()
    assert not at.exception
    assert len(at.selectbox) >= 1
    assert len(at.text_input) >= 1


def test_filter_bar_show_date_false_no_date_input():
    script = _FILTER_BAR_SCRIPT.format(
        categories='["全部", "感測器"]', prefix="t", extra=", show_date=False"
    )
    at = AppTest.from_string(script).run()
    assert not at.exception
    assert len(at.date_input) == 0


def test_filter_bar_show_keyword_false_no_keyword_text_input():
    script = _FILTER_BAR_SCRIPT.format(
        categories='["全部", "感測器"]', prefix="t", extra=", show_keyword=False"
    )
    at = AppTest.from_string(script).run()
    assert not at.exception
    keyword_inputs = [w for w in at.text_input if w.label == "關鍵字"]
    assert len(keyword_inputs) == 0


def test_filter_bar_different_prefixes_namespace_independent():
    script = """\
import streamlit as st
from lib.ui import filter_bar
filter_bar(["全部", "感測器"], key_prefix="a")
filter_bar(["全部", "系統"], key_prefix="b")
"""
    at = AppTest.from_string(script)
    at.session_state["a_category"] = "感測器"
    at.run()
    assert not at.exception
    # prefix-a 的 selectbox（索引 0）改成 "感測器"；prefix-b 的 selectbox（索引 1）應仍為 "全部"
    assert at.selectbox[0].value == "感測器"
    assert at.selectbox[1].value == "全部"


_FILTER_PAGINATION_SCRIPT = """\
import streamlit as st
from lib.ui import filter_bar, pagination_controls, FilterParams

PREV_KEY = "dm_prev_filter"

params = filter_bar(["全部", "感測器", "系統"], key_prefix="dm")
prev = st.session_state.get(PREV_KEY)
if prev is not None and prev != params:
    st.session_state["dm_page"] = 1
st.session_state[PREV_KEY] = params
pagination_controls(total=100, size=20, key_prefix="dm")
"""


def test_filter_bar_change_resets_pagination_page():
    at = AppTest.from_string(_FILTER_PAGINATION_SCRIPT)
    at.session_state["dm_page"] = 2
    at.run()
    assert not at.exception
    assert at.session_state["dm_page"] == 2

    # 改變分類後頁碼應重設為 1
    at.selectbox[0].set_value("感測器").run()
    assert not at.exception
    assert at.session_state["dm_page"] == 1
