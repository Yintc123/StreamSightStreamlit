from __future__ import annotations

import pytest

from lib.system_management import (
    color_log_level,
    format_db_size,
    is_last_super_admin,
    seed_db_status,
    seed_logs,
    seed_users,
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


# --- is_last_super_admin ---

def _users(grades: list) -> list:
    return [{"username": f"u{i}", "grade": g} for i, g in enumerate(grades)]


def test_is_last_super_admin_true_when_only_one():
    users = _users(["super_admin", "editor", "viewer"])
    assert is_last_super_admin(users, "u0") is True


def test_is_last_super_admin_false_when_two_super_admins():
    users = _users(["super_admin", "super_admin", "viewer"])
    assert is_last_super_admin(users, "u0") is False


def test_is_last_super_admin_false_when_target_not_super_admin():
    users = _users(["super_admin", "editor"])
    assert is_last_super_admin(users, "u1") is False


def test_is_last_super_admin_false_when_target_absent():
    users = _users(["super_admin"])
    assert is_last_super_admin(users, "nobody") is False


# --- format_db_size ---

def test_format_db_size_zero():
    assert format_db_size(0) == "0.0 MB"


def test_format_db_size_one_mb():
    assert format_db_size(1024 * 1024) == "1.0 MB"


def test_format_db_size_fifty_mb():
    assert format_db_size(50 * 1024 * 1024) == "50.0 MB"


# --- seed functions deterministic ---

def test_seed_users_returns_list_with_required_keys():
    users = seed_users()
    assert isinstance(users, list)
    assert len(users) >= 1
    for u in users:
        assert "username" in u
        assert "email" in u
        assert "grade" in u
        assert "status" in u


def test_seed_users_includes_all_grades():
    grades = {u["grade"] for u in seed_users()}
    assert "super_admin" in grades
    assert "editor" in grades
    assert "viewer" in grades


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
    assert seed_users() == seed_users()
    assert seed_logs() == seed_logs()
    assert seed_db_status() == seed_db_status()
