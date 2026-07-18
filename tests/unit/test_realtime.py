"""lib/realtime 純函式單元測試。

對應規格 docs/specs/pages/04-realtime-monitor.md §可測試性/TDD（測試 1–11）。
所有函式無 Streamlit 依賴；值生成為決定性（同 (tick, seed) → 同值）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from lib.realtime import (
    CHANNEL,
    MAX_POINTS,
    RECENT_POINTS,
    TIME_FORMAT,
    X_AXIS_LABEL,
    Y_AXIS_LABEL,
    Reading,
    alert_message,
    build_chart,
    generate_stream,
    is_over,
    readings_to_df,
    sample_value,
    summary_metrics,
    trim,
)
from lib.ui import Metric

_TZ = timezone(timedelta(hours=8))
_BASE = datetime(2026, 7, 19, 12, 0, 0, tzinfo=_TZ)


def _reading(i: int, value: float) -> Reading:
    return Reading(ts=_BASE + timedelta(seconds=i), value=value)


# ---------------------------------------------------------------------------
# sample_value（測試 1–3）
# ---------------------------------------------------------------------------

class TestSampleValue:
    def test_deterministic_same_tick(self):
        assert sample_value(5) == sample_value(5)

    def test_within_range(self):
        for tick in range(200):
            v = sample_value(tick)
            assert 0.0 <= v <= 100.0

    def test_rounded_one_decimal(self):
        for tick in range(50):
            v = sample_value(tick)
            assert round(v, 1) == v

    def test_not_constant(self):
        values = {sample_value(tick) for tick in range(50)}
        assert len(values) >= 2


# ---------------------------------------------------------------------------
# generate_stream（測試 4）
# ---------------------------------------------------------------------------

class TestGenerateStream:
    def test_length_and_range(self):
        stream = generate_stream(30)
        assert len(stream) == 30
        assert all(0.0 <= v <= 100.0 for v in stream)

    def test_deterministic(self):
        assert generate_stream(20) == generate_stream(20)

    def test_matches_sample_value_sequence(self):
        stream = generate_stream(10, start_tick=5)
        assert stream == [sample_value(5 + i) for i in range(10)]


# ---------------------------------------------------------------------------
# is_over（測試 5）
# ---------------------------------------------------------------------------

class TestIsOver:
    def test_strictly_greater(self):
        assert is_over(90, 80) is True
        assert is_over(80, 80) is False
        assert is_over(79.9, 80) is False


# ---------------------------------------------------------------------------
# readings_to_df（測試 6–7）
# ---------------------------------------------------------------------------

class TestReadingsToDf:
    def test_empty_returns_empty_df_with_channel_column(self):
        df = readings_to_df([])
        assert df.empty
        assert CHANNEL in df.columns

    def test_index_is_sorted_datetimeindex_single_channel_column(self):
        readings = [_reading(2, 30.0), _reading(0, 10.0), _reading(1, 20.0)]
        df = readings_to_df(readings)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert list(df.index) == sorted(df.index)
        assert list(df.columns) == [CHANNEL]
        assert list(df[CHANNEL]) == [10.0, 20.0, 30.0]


# ---------------------------------------------------------------------------
# summary_metrics（測試 8–10）
# ---------------------------------------------------------------------------

class TestSummaryMetrics:
    def test_empty_returns_empty_list(self):
        assert summary_metrics([], 80) == []

    def test_four_metrics_with_expected_values(self):
        values = [10.0, 50.0, 91.7, 40.0]
        readings = [_reading(i, v) for i, v in enumerate(values)]
        metrics = summary_metrics(readings, 80)
        assert len(metrics) == 4
        assert all(isinstance(m, Metric) for m in metrics)
        current, mx, avg, over = metrics
        assert current.value == values[-1] == 40.0
        assert mx.value == 91.7
        assert avg.value == round(sum(values) / len(values), 1)
        assert over.value == sum(1 for v in values if v > 80)

    def test_over_threshold_current_metric_has_inverse_delta(self):
        readings = [_reading(0, 91.7)]
        current = summary_metrics(readings, 80)[0]
        assert current.delta == round(91.7 - 80, 1)
        assert current.delta_color == "inverse"

    def test_not_over_threshold_current_metric_no_delta(self):
        readings = [_reading(0, 40.0)]
        current = summary_metrics(readings, 80)[0]
        assert current.delta is None
        assert current.delta_color == "off"


# ---------------------------------------------------------------------------
# trim（測試 11）
# ---------------------------------------------------------------------------

class TestTrim:
    def test_over_limit_keeps_last_max(self):
        buffer = [_reading(i, float(i)) for i in range(70)]
        result = trim(buffer, MAX_POINTS)
        assert len(result) == MAX_POINTS
        assert result[0].value == float(70 - MAX_POINTS)
        assert result[-1].value == 69.0

    def test_under_limit_returns_as_is(self):
        buffer = [_reading(i, float(i)) for i in range(30)]
        result = trim(buffer, MAX_POINTS)
        assert len(result) == 30

    def test_does_not_mutate_input(self):
        buffer = [_reading(i, float(i)) for i in range(70)]
        original_len = len(buffer)
        trim(buffer, MAX_POINTS)
        assert len(buffer) == original_len


def test_recent_points_constant_available():
    assert RECENT_POINTS == 15


# ---------------------------------------------------------------------------
# 圖表軸標籤（中文，含單位；單一來源供頁面 import）
# ---------------------------------------------------------------------------

class TestAlertMessage:
    def test_contains_value_and_threshold(self):
        msg = alert_message(91.7, 80)
        assert "告警" in msg
        assert "91.7" in msg
        assert "80" in msg

    def test_no_leading_icon_glyph(self):
        # icon 交給 st.toast(icon=...) 呈現，訊息本文不重複警示符號
        assert not alert_message(50.0, 10).startswith("⚠")


class TestAxisLabels:
    def test_axis_labels_are_chinese_with_unit(self):
        import lib.realtime as rt

        assert rt.X_AXIS_LABEL == "時間（時:分:秒）"
        assert rt.Y_AXIS_LABEL == "數值（0–100）"


class TestBuildChart:
    def _readings(self):
        return [_reading(i, float(i * 10)) for i in range(5)]

    def test_x_axis_is_temporal_with_hms_format_and_titles(self):
        spec = build_chart(self._readings(), "line").to_dict()
        x_axis = spec["encoding"]["x"]["axis"]
        assert spec["encoding"]["x"]["type"] == "temporal"
        assert x_axis["format"] == TIME_FORMAT == "%H:%M:%S"
        assert x_axis["title"] == X_AXIS_LABEL
        assert spec["encoding"]["y"]["axis"]["title"] == Y_AXIS_LABEL

    def test_line_and_bar_marks(self):
        line = build_chart(self._readings(), "line").to_dict()
        bar = build_chart(self._readings(), "bar").to_dict()
        assert line["mark"]["type"] == "line"
        assert bar["mark"]["type"] == "bar"

    def test_empty_readings_does_not_raise(self):
        # 頁面正常走 empty_state 分支不會呼叫；但建構器對空輸入須穩健
        spec = build_chart([], "line").to_dict()
        assert spec["encoding"]["x"]["field"] == "ts"
