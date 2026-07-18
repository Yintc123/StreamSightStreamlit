"""lib/analytics 純函式單元測試。

種子資料（make_seed_records）：200 筆，固定 seed 隨機值（10–999），categories 輪替，
created_at 均勻分佈於 2026-04-19 ~ 2026-07-18（約 90 天）。
期望值統一從 make_seed_records() 動態計算，不硬編碼具體數字。
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from lib.analytics import (
    agg_by_category,
    agg_stats,
    build_export_caption,
    filter_by_category,
    filter_by_date,
    make_excel_bytes,
    records_to_df,
    resample_series,
)
from lib.mock_data_source import make_seed_records


@pytest.fixture
def seed_records():
    return make_seed_records()


@pytest.fixture
def seed_df(seed_records) -> pd.DataFrame:
    """40 筆種子記錄轉 DataFrame（DatetimeIndex=created_at）。"""
    return records_to_df(seed_records)


# ---------------------------------------------------------------------------
# agg_stats
# ---------------------------------------------------------------------------

class TestAggStats:
    def test_returns_sum_mean_max_min(self, seed_records, seed_df):
        values = [r.value for r in seed_records]
        expected_sum = sum(values)
        expected_mean = round(expected_sum / len(values), 2)
        stats = agg_stats(seed_df)
        assert stats["sum"] == pytest.approx(expected_sum)
        assert stats["mean"] == pytest.approx(expected_mean, abs=0.01)
        assert stats["max"] == pytest.approx(max(values))
        assert stats["min"] == pytest.approx(min(values))

    def test_empty_df_all_none(self):
        stats = agg_stats(pd.DataFrame(columns=["value", "category"]))
        assert stats == {"sum": None, "mean": None, "max": None, "min": None}


# ---------------------------------------------------------------------------
# agg_by_category
# ---------------------------------------------------------------------------

class TestAggByCategory:
    def test_groups_four_categories(self, seed_df):
        result = agg_by_category(seed_df)
        assert set(result.index) == {"感測器", "系統", "應用", "網路"}
        assert {"sum", "mean", "max", "min"}.issubset(result.columns)

    def test_category_sums(self, seed_records, seed_df):
        cat_sums: dict = {}
        for r in seed_records:
            cat_sums[r.category] = cat_sums.get(r.category, 0.0) + r.value
        result = agg_by_category(seed_df)
        for cat, expected in cat_sums.items():
            assert result.loc[cat, "sum"] == pytest.approx(expected)

    def test_empty_df_returns_empty(self):
        result = agg_by_category(pd.DataFrame(columns=["value", "category"]))
        assert result.empty


# ---------------------------------------------------------------------------
# resample_series
# ---------------------------------------------------------------------------

class TestResampleSeries:
    def test_daily_covers_full_date_range(self, seed_records, seed_df):
        resampled = resample_series(seed_df, "D")
        unique_dates = len({r.created_at.date() for r in seed_records})
        assert len(resampled) == unique_dates

    def test_daily_total_equals_original(self, seed_records, seed_df):
        resampled = resample_series(seed_df, "D")
        expected_total = sum(r.value for r in seed_records)
        assert resampled.sum() == pytest.approx(expected_total)


# ---------------------------------------------------------------------------
# filter_by_date
# ---------------------------------------------------------------------------

class TestFilterByDate:
    def test_date_from_excludes_earlier(self, seed_records, seed_df):
        date_from = date(2026, 6, 1)
        result = filter_by_date(seed_df, date_from=date_from, date_to=None)
        expected = sum(1 for r in seed_records if r.created_at.date() >= date_from)
        assert len(result) == expected
        assert all(idx.date() >= date_from for idx in result.index)

    def test_date_to_excludes_later(self, seed_records, seed_df):
        date_to = date(2026, 5, 31)
        result = filter_by_date(seed_df, date_from=None, date_to=date_to)
        expected = sum(1 for r in seed_records if r.created_at.date() <= date_to)
        assert len(result) == expected
        assert all(idx.date() <= date_to for idx in result.index)

    def test_both_bounds_narrow_range(self, seed_records, seed_df):
        date_from, date_to = date(2026, 5, 1), date(2026, 6, 30)
        result = filter_by_date(seed_df, date_from=date_from, date_to=date_to)
        expected = sum(
            1 for r in seed_records
            if date_from <= r.created_at.date() <= date_to
        )
        assert len(result) == expected

    def test_none_bounds_return_all(self, seed_df):
        result = filter_by_date(seed_df, date_from=None, date_to=None)
        assert len(result) == len(seed_df)


# ---------------------------------------------------------------------------
# filter_by_category
# ---------------------------------------------------------------------------

class TestFilterByCategory:
    def test_specific_category(self, seed_records, seed_df):
        result = filter_by_category(seed_df, "感測器")
        expected = sum(1 for r in seed_records if r.category == "感測器")
        assert len(result) == expected
        assert (result["category"] == "感測器").all()

    def test_all_returns_full_df(self, seed_df):
        result = filter_by_category(seed_df, "全部")
        assert len(result) == len(seed_df)


# ---------------------------------------------------------------------------
# build_export_caption
# ---------------------------------------------------------------------------

class TestBuildExportCaption:
    def test_no_dates_shows_category_and_count(self):
        result = build_export_caption("全部", None, None, 200)
        assert result == "目前篩選：分類=全部，共 200 筆"

    def test_both_dates_included(self):
        result = build_export_caption("感測器", date(2026, 4, 1), date(2026, 6, 30), 50)
        assert "期間 2026/04/01 ~ 2026/06/30" in result
        assert "分類=感測器" in result
        assert "共 50 筆" in result

    def test_only_date_from_uses_dash_for_end(self):
        result = build_export_caption("全部", date(2026, 6, 1), None, 100)
        assert "期間 2026/06/01 ~ —" in result
        assert "共 100 筆" in result

    def test_only_date_to_uses_dash_for_start(self):
        result = build_export_caption("全部", None, date(2026, 6, 30), 80)
        assert "期間 — ~ 2026/06/30" in result
        assert "共 80 筆" in result


# ---------------------------------------------------------------------------
# make_excel_bytes
# ---------------------------------------------------------------------------

class TestMakeExcelBytes:
    def test_returns_non_empty_bytes(self, seed_df):
        result = make_excel_bytes(seed_df.reset_index())
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_empty_df_does_not_raise(self):
        result = make_excel_bytes(pd.DataFrame(columns=["value", "category"]))
        assert isinstance(result, bytes)
