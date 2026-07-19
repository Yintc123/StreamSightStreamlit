from __future__ import annotations

import pytest
import streamlit as st

from lib import errors
from lib.api_client import ApiError
from lib.models import NotAuthenticated, PermissionDenied, RecordNotFound, ValidationError


# --- to_user_message 純函式(error-handling §7 測 1–7) ---

def test_permission_denied_is_error_without_request_id():
    view = errors.to_user_message(PermissionDenied())
    assert view.level == "error"
    assert view.request_id is None


def test_record_not_found_is_warning_without_request_id():
    view = errors.to_user_message(RecordNotFound())
    assert view.level == "warning"
    assert view.request_id is None


def test_validation_error_is_error_with_reason():
    view = errors.to_user_message(ValidationError("category 不合法"))
    assert view.level == "error"
    assert "category 不合法" in view.text
    assert view.request_id is None


def test_apierror_timeout_is_error_with_request_id_placeholder():
    view = errors.to_user_message(ApiError("逾時", status=None, request_id="st-abc"))
    assert view.level == "error"
    assert view.request_id == "st-abc"
    assert "錯誤代碼" in view.text


def test_apierror_5xx_carries_request_id():
    view = errors.to_user_message(ApiError("boom", status=500, request_id="st-500"))
    assert view.level == "error"
    assert view.request_id == "st-500"


def test_request_id_policy_domain_none_apierror_present():
    for exc in (PermissionDenied(), RecordNotFound(), ValidationError("x")):
        assert errors.to_user_message(exc).request_id is None
    assert errors.to_user_message(ApiError("x", status=500, request_id="st-1")).request_id == "st-1"


def test_backend_packet_fallback_code_none_does_not_crash():
    view = errors.to_user_message(ApiError("x", status=503, request_id="st-2", code=None))
    assert view.level == "error"
    assert view.code is None


def test_not_authenticated_reraises_from_to_user_message():
    """NotAuthenticated 不翻成 ErrorView，直接 re-raise（error-handling §3）。"""
    with pytest.raises(NotAuthenticated):
        errors.to_user_message(NotAuthenticated())


def test_not_authenticated_reraises_from_render_error(monkeypatch, fake_session):
    """render_error 遇 NotAuthenticated 不呼 st.* 而是 re-raise。"""
    called = []
    for level in ("error", "warning", "info"):
        monkeypatch.setattr(st, level, lambda msg, lvl=level: called.append(lvl))
    with pytest.raises(NotAuthenticated):
        errors.render_error(NotAuthenticated())
    assert called == [], "render_error 不應呼叫任何 st.error/warning/info"


# --- render_error 薄 UI 綁定 ---

@pytest.fixture
def fake_session(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(st, "session_state", store)
    return store


def test_render_error_apierror_calls_st_error_and_writes_last_request_id(monkeypatch, fake_session):
    captured = {}
    monkeypatch.setattr(st, "error", lambda msg: captured.__setitem__("error", msg))
    errors.render_error(ApiError("x", status=500, request_id="st-9"))
    assert "錯誤代碼:st-9" in captured["error"]
    assert fake_session["last_request_id"] == "st-9"


def test_render_error_permission_denied_no_request_id_written(monkeypatch, fake_session):
    monkeypatch.setattr(st, "error", lambda msg: None)
    errors.render_error(PermissionDenied())
    assert "last_request_id" not in fake_session
