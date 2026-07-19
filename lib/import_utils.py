"""匯入解析工具：CSV / JSON → list[dict]。

parse_csv_bytes / parse_json_bytes 均為純函式（不依賴 Streamlit），
供頁面呼叫後再傳入 ds.bulk_create()。

回傳值：(rows, error_msg)
  - 成功：(list[dict], None)
  - 超過上限 / 格式錯誤：([], str)
"""
from __future__ import annotations

import csv
import io
import json
from typing import List, Optional, Tuple

from lib.models import BULK_MAX_ROWS

_REQUIRED_COLS = {"title", "value", "category"}


def parse_csv_bytes(content: bytes) -> Tuple[List[dict], Optional[str]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], None
    fieldnames = {f.strip() for f in reader.fieldnames}
    if not _REQUIRED_COLS.issubset(fieldnames):
        missing = _REQUIRED_COLS - fieldnames
        return [], f"CSV 缺少必要欄位：{', '.join(sorted(missing))}"

    rows = list(reader)
    if len(rows) > BULK_MAX_ROWS:
        return [], f"單檔最多 {BULK_MAX_ROWS} 列，本次共 {len(rows)} 列"

    result = []
    for row in rows:
        try:
            value = float(row.get("value", "").strip())
        except (ValueError, AttributeError):
            value = 0.0
        result.append({
            "title": row.get("title", "").strip(),
            "value": value,
            "category": row.get("category", "").strip(),
            "note": row.get("note", "").strip() if "note" in row else "",
        })
    return result, None


def parse_json_bytes(content: bytes) -> Tuple[List[dict], Optional[str]]:
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return [], f"JSON 格式錯誤：{e}"

    if not isinstance(data, list):
        return [], "JSON 需為物件陣列（頂層 [...]）"

    if len(data) > BULK_MAX_ROWS:
        return [], f"單檔最多 {BULK_MAX_ROWS} 列，本次共 {len(data)} 列"

    result = []
    for item in data:
        if not isinstance(item, dict):
            result.append({"title": "", "value": 0.0, "category": "", "note": ""})
            continue
        try:
            value = float(item.get("value", 0))
        except (ValueError, TypeError):
            value = 0.0
        result.append({
            "title": str(item.get("title", "")).strip(),
            "value": value,
            "category": str(item.get("category", "")).strip(),
            "note": str(item.get("note", "")).strip(),
        })
    return result, None
