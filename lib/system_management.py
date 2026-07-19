"""系統管理頁純函式與 mock 靜態種子。

見規格 docs/specs/pages/06-admin.md §lib/system_management.py 純函式契約。
所有函式無 Streamlit 依賴，可直接單元測試。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional, Tuple

from lib.models import LogEntry


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


def format_log_ts(ts_ms: int) -> str:
    """epoch ms（UTC）→ 'YYYY-MM-DD HH:MM:SS' UTC 字串。"""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def date_to_epoch_ms(d: date) -> int:
    """date → UTC 當日 00:00:00 epoch ms。"""
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def date_range_to_ms(d_from: date, d_to: date) -> Tuple[int, int]:
    """(起, 迄) date → (since_ms, until_ms)；until 為 d_to 當日 23:59:59.999。"""
    since_ms = date_to_epoch_ms(d_from)
    until_ms = date_to_epoch_ms(d_to) + 86_400_000 - 1
    return since_ms, until_ms


def log_entries_to_rows(entries: List) -> List[dict]:
    """LogEntry list → display rows（供 st.dataframe）；request_id None 顯示 '—'。"""
    return [
        {
            "時間":       format_log_ts(e.ts),
            "等級":       e.level,
            "模組":       e.logger,
            "訊息":       e.message,
            "Request ID": e.request_id if e.request_id is not None else "—",
        }
        for e in entries
    ]


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


def seed_logs() -> List[LogEntry]:
    """mock 靜態日誌，格式對齊後端 LogEntry schema（含 INFO / WARNING / ERROR；決定性）。"""
    return [
        LogEntry(ts=1704067200000, level="INFO",    logger="app.api.routers.auth",    message="login success",                request_id="req-001"),
        LogEntry(ts=1704070800000, level="INFO",    logger="app.services.record",     message="record created id=42",         request_id="req-002"),
        LogEntry(ts=1704074400000, level="WARNING", logger="app.core.auth.jwt",       message="token near expiry",            request_id="req-003"),
        LogEntry(ts=1704078000000, level="WARNING", logger="app.services.monitoring", message="log flush failed, retry",      request_id=None),
        LogEntry(ts=1704081600000, level="ERROR",   logger="app.core.db.session",     message="db connection pool exhausted", request_id="req-005", module="session", func="get_session", line=42),
    ]


def seed_db_status() -> dict:
    """mock 靜態伺服器狀態（決定性）。"""
    return {
        "cpu_percent":    45.2,
        "memory_percent": 62.8,
        "connections":    5,
    }
