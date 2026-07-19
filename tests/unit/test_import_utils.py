"""TDD 8-8：匯入解析純函式測試。

parse_csv_bytes(content: bytes) -> tuple[list[dict], str | None]
  成功 → (rows, None)
  超過 1000 列 → ([], error_msg)
  格式錯誤 → ([], error_msg)
"""
from __future__ import annotations

import io
import pytest

from lib.import_utils import parse_csv_bytes, parse_json_bytes


def _make_csv(*rows: dict) -> bytes:
    header = "title,value,category,note"
    lines = [header] + [
        f"{r.get('title','')},{r.get('value', 1.0)},{r.get('category','感測器')},{r.get('note','')}"
        for r in rows
    ]
    return "\n".join(lines).encode("utf-8")


# ── parse_csv_bytes ────────────────────────────────────────────────────

class TestParseCsvBytes:
    def test_valid_csv_returns_rows_and_no_error(self):
        content = _make_csv(
            {"title": "A", "value": 1.0, "category": "感測器"},
            {"title": "B", "value": 2.5, "category": "系統"},
        )
        rows, err = parse_csv_bytes(content)
        assert err is None
        assert len(rows) == 2
        assert rows[0]["title"] == "A"
        assert rows[0]["value"] == pytest.approx(1.0)
        assert rows[0]["category"] == "感測器"

    def test_note_field_parsed(self):
        content = _make_csv({"title": "X", "value": 3.0, "category": "應用", "note": "備註內容"})
        rows, err = parse_csv_bytes(content)
        assert err is None
        assert rows[0]["note"] == "備註內容"

    def test_missing_note_defaults_to_empty_string(self):
        """CSV 無 note 欄或空值 → 預設 ''。"""
        raw = "title,value,category\n有標題,1.0,感測器".encode("utf-8")
        rows, err = parse_csv_bytes(raw)
        assert err is None
        assert rows[0]["note"] == ""

    def test_value_parsed_as_float(self):
        content = _make_csv({"title": "V", "value": "99.9", "category": "網路"})
        rows, err = parse_csv_bytes(content)
        assert err is None
        assert isinstance(rows[0]["value"], float)
        assert rows[0]["value"] == pytest.approx(99.9)

    def test_over_1000_rows_returns_error(self):
        rows_data = [{"title": f"r{i}", "value": i, "category": "感測器"} for i in range(1001)]
        content = _make_csv(*rows_data)
        rows, err = parse_csv_bytes(content)
        assert rows == []
        assert err is not None
        assert "1000" in err

    def test_empty_csv_returns_empty_rows_no_error(self):
        content = b"title,value,category,note\n"
        rows, err = parse_csv_bytes(content)
        assert err is None
        assert rows == []

    def test_missing_required_column_returns_error(self):
        """缺少 title 欄位 → 整體拒絕（格式錯誤）。"""
        content = "value,category\n1.0,感測器\n".encode("utf-8")
        rows, err = parse_csv_bytes(content)
        assert rows == []
        assert err is not None


# ── parse_json_bytes ───────────────────────────────────────────────────

class TestParseJsonBytes:
    def test_valid_json_array_returns_rows(self):
        import json
        data = [
            {"title": "J1", "value": 1.0, "category": "感測器"},
            {"title": "J2", "value": 2.0, "category": "系統", "note": "json備註"},
        ]
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        rows, err = parse_json_bytes(content)
        assert err is None
        assert len(rows) == 2
        assert rows[1]["note"] == "json備註"

    def test_invalid_json_returns_error(self):
        content = b"not json"
        rows, err = parse_json_bytes(content)
        assert rows == []
        assert err is not None

    def test_json_not_array_returns_error(self):
        import json
        content = json.dumps({"title": "X"}).encode("utf-8")
        rows, err = parse_json_bytes(content)
        assert rows == []
        assert err is not None

    def test_json_over_1000_rows_returns_error(self):
        import json
        data = [{"title": f"r{i}", "value": i, "category": "感測器"} for i in range(1001)]
        content = json.dumps(data).encode("utf-8")
        rows, err = parse_json_bytes(content)
        assert rows == []
        assert err is not None
        assert "1000" in err


class TestSummarizeImport:
    """summarize_import：ImportResult → (level, message, detail) 顯示三元組。"""

    def test_all_success(self):
        from lib.import_utils import summarize_import
        from lib.models import ImportResult

        level, message, detail = summarize_import(ImportResult(created=3, errors=[]))
        assert level == "success"
        assert "3" in message
        assert detail is None

    def test_partial_errors_lists_row_numbers(self):
        from lib.import_utils import summarize_import
        from lib.models import ImportResult, RowError

        result = ImportResult(
            created=1,
            errors=[RowError(row_index=2, reason="bad"), RowError(row_index=4, reason="bad")],
        )
        level, message, detail = summarize_import(result)
        assert level == "warning"
        assert "1" in message and "2" in message   # 成功 1 筆、錯誤 2 筆
        assert detail is not None
        assert "3" in detail and "5" in detail     # row_index+1（1-based 列號）

    def test_more_than_five_errors_truncated_with_ellipsis(self):
        from lib.import_utils import summarize_import
        from lib.models import ImportResult, RowError

        result = ImportResult(
            created=0,
            errors=[RowError(row_index=i, reason="bad") for i in range(6)],
        )
        _, _, detail = summarize_import(result)
        assert detail.endswith("…")
        assert "6" not in detail.replace("錯誤", "")  # 只列前 5 列（列號 1–5）
