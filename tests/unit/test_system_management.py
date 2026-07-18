from __future__ import annotations

from lib.system_management import (
    color_log_level,
    format_db_size,
    seed_db_status,
    seed_logs,
)


# --- color_log_level ---

def test_color_log_level_error_returns_red():
    assert color_log_level("ERROR") == "#FF4B4B"


def test_color_log_level_warning_returns_orange():
    assert color_log_level("WARNING") == "#FFA500"


def test_color_log_level_info_returns_green():
    assert color_log_level("INFO") == "#21C354"


def test_color_log_level_unknown_returns_neutral():
    result = color_log_level("DEBUG")
    assert result  # 非空字串（中性色）
    assert result not in ("#FF4B4B", "#FFA500", "#21C354")


# --- format_db_size ---

def test_format_db_size_zero():
    assert format_db_size(0) == "0.0 MB"


def test_format_db_size_one_mb():
    assert format_db_size(1024 * 1024) == "1.0 MB"


def test_format_db_size_fifty_mb():
    assert format_db_size(50 * 1024 * 1024) == "50.0 MB"


# --- seed functions deterministic ---

def test_seed_logs_returns_list_with_required_keys():
    logs = seed_logs()
    assert isinstance(logs, list)
    assert len(logs) >= 1
    for log in logs:
        assert "time" in log
        assert "user" in log
        assert "action" in log
        assert "result" in log
        assert "level" in log


def test_seed_logs_includes_all_levels():
    levels = {l["level"] for l in seed_logs()}
    assert "INFO" in levels
    assert "WARNING" in levels
    assert "ERROR" in levels


def test_seed_db_status_returns_dict_with_required_keys():
    db = seed_db_status()
    assert "connected" in db
    assert "total_rows" in db
    assert "size_bytes" in db
    assert isinstance(db["connected"], bool)
    assert isinstance(db["total_rows"], int)
    assert isinstance(db["size_bytes"], int)


def test_seed_functions_are_deterministic():
    assert seed_logs() == seed_logs()
    assert seed_db_status() == seed_db_status()
