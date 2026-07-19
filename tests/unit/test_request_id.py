from __future__ import annotations

import logging
import uuid

from lib import request_id
from lib.config import get_settings


# --- new_request_id(§6 測 1–3) ---

def test_new_request_id_format_and_uniqueness():
    rid = request_id.new_request_id()
    assert rid.startswith("st-")
    hex_part = rid[len("st-"):]
    assert len(hex_part) == 32
    int(hex_part, 16)  # 純 hex
    assert request_id.new_request_id() != request_id.new_request_id()


def test_prefix_is_configurable():
    assert request_id.new_request_id(prefix="dash").startswith("dash-")


def test_generator_is_injectable_for_determinism():
    fixed = uuid.UUID("00000000000000000000000000000001")
    rid = request_id.new_request_id(gen=lambda: fixed)
    assert rid == "st-" + fixed.hex


# --- with_request_id(§6 測 4–5) ---

def test_with_request_id_returns_new_dict_not_mutating():
    original = {"Accept": "application/json"}
    out = request_id.with_request_id(original, "st-abc")
    assert out["X-Request-ID"] == "st-abc"
    assert "X-Request-ID" not in original  # 不就地修改


def test_with_request_id_does_not_overwrite_existing_case_insensitive():
    headers = {"x-request-id": "upstream-1"}
    out = request_id.with_request_id(headers, "st-new")
    # 沿用既有(大小寫不敏感),不覆寫
    assert out["x-request-id"] == "upstream-1"
    assert "st-new" not in out.values()


# --- read_request_id(§6 測 6) ---

def test_read_request_id_case_insensitive():
    assert request_id.read_request_id({"x-request-id": "st-1"}) == "st-1"
    assert request_id.read_request_id({"No-Id": "x"}) is None


# --- ContextVar(§6 測 7) ---

def test_set_and_get_current():
    request_id.set_current("st-ctx")
    assert request_id.get_current() == "st-ctx"
    request_id.set_current(None)
    assert request_id.get_current() is None


# --- init_logging(冪等 + filter 注入 rid) ---

# --- config 整合(request-id §2、request-id.md §31、config §3.6) ---

def test_new_request_id_uses_config_prefix(monkeypatch):
    """new_request_id() 預設前綴來自 config.request_id_prefix（request-id §2）。"""
    monkeypatch.setenv("REQUEST_ID_PREFIX", "dash")
    rid = request_id.new_request_id()
    assert rid.startswith("dash-"), f"預期前綴 'dash-'，實際: {rid}"


def test_with_request_id_uses_config_header(monkeypatch):
    """with_request_id() 預設 header 名稱來自 config.request_id_header（request-id §2）。"""
    monkeypatch.setenv("REQUEST_ID_HEADER", "X-Trace-ID")
    out = request_id.with_request_id({}, "st-abc")
    assert "X-Trace-ID" in out, f"預期 header 'X-Trace-ID'，實際 keys: {list(out.keys())}"


# --- init_logging(冪等 + filter 注入 rid) ---

def test_init_logging_idempotent_and_injects_request_id():
    request_id.init_logging()
    request_id.init_logging()  # 第二次不重複掛
    logger = logging.getLogger("streamsight.api")
    ours = [f for f in logger.filters if getattr(f, "_streamsight", False)]
    assert len(ours) == 1

    request_id.set_current("st-log")
    record = logging.LogRecord("streamsight.api", logging.INFO, "", 0, "m", None, None)
    for filt in logger.filters:
        filt.filter(record)
    assert record.request_id == "st-log"
    request_id.set_current(None)
