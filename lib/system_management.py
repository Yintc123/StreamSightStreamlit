"""系統管理頁純函式與 mock 靜態種子。

見規格 docs/specs/pages/06-admin.md §lib/system_management.py 純函式契約。
所有函式無 Streamlit 依賴，可直接單元測試。
"""
from __future__ import annotations

from typing import List, Optional


def color_log_level(level: str) -> str:
    """日誌等級 → CSS 色碼（供 st.markdown 著色）；未知等級回中性灰。"""
    return {
        "ERROR":   "#FF4B4B",
        "WARNING": "#FFA500",
        "INFO":    "#21C354",
    }.get(level, "#808495")


def format_db_size(size_bytes: int) -> str:
    """位元組 → '{:.1f} MB' 字串；0 → '0.0 MB'。"""
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_percent(value: Optional[float]) -> str:
    """百分比 → '{:.1f}%' 字串；None（exporter 未就緒）→ 'N/A'。"""
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def parse_infra_snapshot(snapshots: List[dict]) -> dict:
    """從後端 InfraHistoryResponse.snapshots 取最新一筆（最後一筆）。

    空 list（後端尚無採樣）→ 全部 None；缺欄位以 .get() 防守。
    cpu_percent / db_connections 可能為 None（exporter 未就緒）。
    """
    if not snapshots:
        return {"cpu_percent": None, "memory_percent": None, "db_connections": None}
    latest = snapshots[-1]
    return {
        "cpu_percent":    latest.get("cpu_percent"),
        "memory_percent": latest.get("memory_percent"),
        "db_connections": latest.get("db_connections"),
    }


def fetch_infra_snapshot(client, base_url: str) -> dict:
    """呼叫 GET /monitoring/infra 並取最新快照；API 失敗向上拋例外（由頁面 render_error）。"""
    data = client.request("GET", f"{base_url}/monitoring/infra")
    return parse_infra_snapshot(data.get("snapshots", []))


def seed_logs() -> List[dict]:
    """mock 靜態日誌（含 INFO / WARNING / ERROR；決定性）。"""
    return [
        {"time": "2024-01-01 08:00", "user": "alice",  "action": "login",          "result": "success",          "level": "INFO"},
        {"time": "2024-01-01 09:00", "user": "bob",    "action": "update_record",  "result": "success",          "level": "INFO"},
        {"time": "2024-01-01 10:00", "user": "carol",  "action": "delete_record",  "result": "permission_denied","level": "WARNING"},
        {"time": "2024-01-01 11:00", "user": "alice",  "action": "import_records", "result": "partial_fail",     "level": "WARNING"},
        {"time": "2024-01-01 12:00", "user": "system", "action": "db_backup",      "result": "failed",           "level": "ERROR"},
    ]


def seed_db_status() -> dict:
    """mock 靜態伺服器狀態（決定性）。"""
    return {
        "cpu_percent":    45.2,
        "memory_percent": 62.8,
        "connections":    5,
    }
