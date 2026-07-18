"""tests/unit/test_ui.py — lib/ui.py 純函式單元測試。"""
from __future__ import annotations

from lib.ui import FilterParams, Metric, _clamp_page, _page_caption


# --- Phase 1: 純資料型別 ---

def test_filter_params_defaults():
    fp = FilterParams()
    assert fp.category == "全部"
    assert fp.keyword == ""
    assert fp.date_from is None
    assert fp.date_to is None


def test_metric_defaults():
    m = Metric(label="總計", value=10)
    assert m.delta is None
    assert m.delta_color == "normal"
    assert m.help is None


# --- Phase 2: 純函式 ---

def test_page_caption():
    assert _page_caption(1, 5, 47) == "第 1 / 5 頁 · 共 47 筆"


def test_clamp_page_lower_bound():
    assert _clamp_page(0, 3) == 1


def test_clamp_page_upper_bound():
    assert _clamp_page(10, 3) == 3


def test_clamp_page_in_range():
    assert _clamp_page(2, 3) == 2
