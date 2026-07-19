"""tests/unit/test_ui.py — lib/ui.py 純函式單元測試。"""
from __future__ import annotations

from datetime import date

from lib.ui import FilterParams, Metric, _clamp_page, _page_caption, default_date_range


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


# --- Phase 3: 落地頁預設時間區間（05-analytics §共用篩選列） ---

def test_default_date_range_last_7_days():
    """『最近 7 天』= (today - 7, today)，兩端齊備供 filter_bar 落地預設。"""
    frm, to = default_date_range(date(2026, 7, 19), 7)
    assert to == date(2026, 7, 19)
    assert frm == date(2026, 7, 12)


def test_default_date_range_is_pure_and_span_matches_days():
    frm, to = default_date_range(date(2026, 1, 31), 30)
    assert (to - frm).days == 30
