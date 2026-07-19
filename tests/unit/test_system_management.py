from __future__ import annotations

from lib.system_management import (
    color_log_level,
    format_db_size,
    fetch_infra_snapshot,
    format_percent,
    parse_infra_snapshot,
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


# --- format_percent ---

def test_format_percent_normal():
    assert format_percent(45.2) == "45.2%"


def test_format_percent_zero():
    assert format_percent(0.0) == "0.0%"


def test_format_percent_none():
    assert format_percent(None) == "N/A"


# --- parse_infra_snapshot ---

def test_parse_infra_snapshot_full():
    snapshots = [{"cpu_percent": 45.2, "memory_percent": 62.8, "db_connections": 5}]
    result = parse_infra_snapshot(snapshots)
    assert result["cpu_percent"] == 45.2
    assert result["memory_percent"] == 62.8
    assert result["db_connections"] == 5


def test_parse_infra_snapshot_with_none_fields():
    """exporter 未就緒 → cpu_percent / db_connections 為 None，memory_percent 仍有值。"""
    snapshots = [{"cpu_percent": None, "memory_percent": 62.8, "db_connections": None}]
    result = parse_infra_snapshot(snapshots)
    assert result["cpu_percent"] is None
    assert result["db_connections"] is None
    assert result["memory_percent"] == 62.8


def test_parse_infra_snapshot_empty_list():
    """後端剛啟動、尚無採樣 → 全部 None。"""
    result = parse_infra_snapshot([])
    assert result == {"cpu_percent": None, "memory_percent": None, "db_connections": None}


def test_parse_infra_snapshot_takes_latest():
    """snapshots 由舊到新 → 取最後一筆。"""
    snapshots = [
        {"cpu_percent": 10.0, "memory_percent": 20.0, "db_connections": 1},
        {"cpu_percent": 50.0, "memory_percent": 70.0, "db_connections": 9},
    ]
    result = parse_infra_snapshot(snapshots)
    assert result["cpu_percent"] == 50.0
    assert result["memory_percent"] == 70.0
    assert result["db_connections"] == 9


# --- fetch_infra_snapshot ---

class _FakeClient:
    """記錄呼叫參數並回傳固定回應的 ApiClient 替身。"""

    def __init__(self, response: dict):
        self.response = response
        self.calls: list = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        return self.response


def test_fetch_infra_snapshot_calls_monitoring_infra_and_parses():
    client = _FakeClient({"snapshots": [
        {"cpu_percent": 45.2, "memory_percent": 62.8, "db_connections": 5},
    ]})
    result = fetch_infra_snapshot(client, "http://api.local")
    assert client.calls == [("GET", "http://api.local/monitoring/infra")]
    assert result == {"cpu_percent": 45.2, "memory_percent": 62.8, "db_connections": 5}


def test_fetch_infra_snapshot_missing_snapshots_key_returns_all_none():
    """後端回應缺 snapshots 欄位 → 防守為全 None，不拋 KeyError。"""
    client = _FakeClient({})
    result = fetch_infra_snapshot(client, "http://api.local")
    assert result == {"cpu_percent": None, "memory_percent": None, "db_connections": None}


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
    assert "cpu_percent" in db
    assert "memory_percent" in db
    assert "connections" in db
    assert isinstance(db["cpu_percent"], float)
    assert isinstance(db["memory_percent"], float)
    assert isinstance(db["connections"], int)


def test_seed_functions_are_deterministic():
    assert seed_logs() == seed_logs()
    assert seed_db_status() == seed_db_status()
