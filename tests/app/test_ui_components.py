"""tests/app/test_ui_components.py — lib/ui.py UI 元件 AppTest 頁面行為測試。"""
from __future__ import annotations

from streamlit.testing.v1 import AppTest

from lib.ui import Metric


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
