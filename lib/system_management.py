"""系統管理頁純函式與 mock 靜態種子。

見規格 docs/specs/pages/06-admin.md §lib/system_management.py 純函式契約。
所有函式無 Streamlit 依賴，可直接單元測試。
"""
from __future__ import annotations

from typing import List


def color_log_level(level: str) -> str:
    """日誌等級 → CSS 色碼（供 st.markdown 著色）；未知等級回中性灰。"""
    return {
        "ERROR":   "#FF4B4B",
        "WARNING": "#FFA500",
        "INFO":    "#21C354",
    }.get(level, "#808495")


def is_last_super_admin(users: List[dict], target_username: str) -> bool:
    """target 為唯一 super_admin 時回 True（擋降級 / 停用保護）。"""
    super_admins = [u for u in users if u.get("grade") == "super_admin"]
    if len(super_admins) != 1:
        return False
    return super_admins[0]["username"] == target_username


def format_db_size(size_bytes: int) -> str:
    """位元組 → '{:.1f} MB' 字串；0 → '0.0 MB'。"""
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def seed_users() -> List[dict]:
    """mock 靜態使用者清單（決定性，不依賴時鐘）。"""
    return [
        {"username": "alice",  "email": "alice@example.com",  "grade": "super_admin", "created_at": "2024-01-01", "status": "active"},
        {"username": "bob",    "email": "bob@example.com",    "grade": "editor",      "created_at": "2024-01-02", "status": "active"},
        {"username": "carol",  "email": "carol@example.com",  "grade": "viewer",      "created_at": "2024-01-03", "status": "active"},
    ]


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
    """mock 靜態 DB 狀態（決定性）。"""
    return {
        "connected":       True,
        "total_rows":      1250,
        "size_bytes":      50 * 1024 * 1024,  # 50 MB
        "history_records": [],
    }
