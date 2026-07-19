from __future__ import annotations

import httpx
import pytest

from lib.api_client import ApiClient, ApiDataSource, ApiError
from lib.models import (
    NotAuthenticated,
    PermissionDenied,
    RecordNotFound,
    ValidationError,
)


def make_client(handler, **kw):
    """以 httpx.MockTransport 注入假回應,不打真後端。"""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    kw.setdefault("get_token", lambda: "tok")
    kw.setdefault("refresh_token", lambda: "tok2")
    kw.setdefault("raw_cookie", lambda: "cookie-raw")
    kw.setdefault("sleep", lambda _s: None)
    return ApiClient(client=client, **kw)


def json_handler(status, payload=None):
    def handler(request):
        return httpx.Response(status, json=payload)
    return handler


# --- 狀態 → 例外映射(§9 測 1) ---

@pytest.mark.parametrize(
    "status,exc",
    [
        (400, ValidationError),
        (422, ValidationError),
        (403, PermissionDenied),
        (404, RecordNotFound),
    ],
)
def test_status_maps_to_domain_exceptions(status, exc):
    c = make_client(json_handler(status, {"error": {"message": "x"}}))
    with pytest.raises(exc):
        c.request("GET", "http://test/records/1")


def test_500_maps_to_apierror_with_status():
    c = make_client(json_handler(500, {"error": {"message": "boom"}}))
    with pytest.raises(ApiError) as ei:
        c.request("GET", "http://test/records")
    assert ei.value.status == 500
    assert ei.value.request_id is not None


# --- 逾時 / 連線錯誤 → ApiError(status=None)且帶 request_id(§9 測 2) ---

def test_timeout_becomes_apierror_none_status():
    def handler(request):
        raise httpx.TimeoutException("t", request=request)

    with pytest.raises(ApiError) as ei:
        make_client(handler).request("GET", "http://test/records")
    assert ei.value.status is None
    assert ei.value.request_id is not None


def test_transport_error_becomes_apierror():
    def handler(request):
        raise httpx.ConnectError("nope", request=request)

    with pytest.raises(ApiError) as ei:
        make_client(handler).request("GET", "http://test/records")
    assert ei.value.status is None


# --- X-Request-ID(§9 測 3) ---

def test_each_call_sends_unique_request_id():
    seen = []

    def handler(request):
        seen.append(request.headers.get("X-Request-ID"))
        return httpx.Response(200, json={})

    c = make_client(handler)
    c.request("GET", "http://test/a")
    c.request("GET", "http://test/b")
    assert all(seen) and seen[0] != seen[1]


# --- 認證方式 + 204(§9 測 8) ---

def test_bearer_auth_sends_authorization_header():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={})

    make_client(handler).request("GET", "http://test/records", auth="bearer")
    assert captured["auth"] == "Bearer tok"


def test_cookie_auth_forwards_cookie_without_bearer():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("Authorization")
        captured["cookie"] = request.headers.get("Cookie")
        return httpx.Response(200, json={})

    make_client(handler).request("GET", "http://test/session", auth="cookie")
    assert captured["auth"] is None
    assert "cookie-raw" in (captured["cookie"] or "")


def test_extra_headers_are_sent_in_request():
    """extra_headers 的 key-value 被送入實際 HTTP 請求 headers。"""
    captured = {}

    def handler(request):
        captured["csrf"] = request.headers.get("X-CSRF-Token")
        return httpx.Response(200, json={})

    make_client(handler).request(
        "POST", "http://test/logout", auth="cookie", extra_headers={"X-CSRF-Token": "tok-csrf"}
    )
    assert captured["csrf"] == "tok-csrf"


def test_204_returns_none():
    c = make_client(lambda request: httpx.Response(204))
    assert c.request("DELETE", "http://test/records/1") is None


# --- 401 reactive refresh(§9 測 5) ---

def test_401_triggers_single_refresh_then_retries_with_new_token():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(401, json={"error": {"message": "expired"}})
        assert request.headers["Authorization"] == "Bearer tok2"
        return httpx.Response(200, json={"ok": True})

    refreshed = {"n": 0}

    def refresh():
        refreshed["n"] += 1
        return "tok2"

    data = make_client(handler, refresh_token=refresh).request("GET", "http://test/records")
    assert data == {"ok": True}
    assert refreshed["n"] == 1


def test_second_401_raises_not_authenticated():
    c = make_client(json_handler(401, {"error": {"message": "no"}}), refresh_token=lambda: "tok2")
    with pytest.raises(NotAuthenticated):
        c.request("GET", "http://test/records")


def test_cookie_auth_401_does_not_refresh():
    refreshed = {"n": 0}

    def refresh():
        refreshed["n"] += 1
        return "x"

    c = make_client(json_handler(401, {}), refresh_token=refresh)
    with pytest.raises(NotAuthenticated):
        c.request("GET", "http://test/session", auth="cookie")
    assert refreshed["n"] == 0


# --- 網路重試:GET 冪等重試、非冪等不重試(§9 測 6) ---

def _counting_status_handler(status, counter):
    def handler(request):
        counter["n"] += 1
        return httpx.Response(status, json={})

    return handler


def test_get_retries_on_503_up_to_limit():
    counter = {"n": 0}
    c = make_client(_counting_status_handler(503, counter), retry_max=2)
    with pytest.raises(ApiError) as ei:
        c.request("GET", "http://test/records")
    assert ei.value.status == 503
    assert counter["n"] == 3  # 1 次原始 + 2 次重試


def test_post_does_not_retry_on_503():
    counter = {"n": 0}
    c = make_client(_counting_status_handler(503, counter), retry_max=2)
    with pytest.raises(ApiError):
        c.request("POST", "http://test/records", json={"a": 1})
    assert counter["n"] == 1  # 非冪等不重試


def test_get_retries_on_connection_error_post_does_not():
    for method, expected in (("GET", 3), ("POST", 1)):
        counter = {"n": 0}

        def handler(request):
            counter["n"] += 1
            raise httpx.ConnectError("x", request=request)

        c = make_client(handler, retry_max=2)
        with pytest.raises(ApiError):
            c.request(method, "http://test/records", json=None if method == "GET" else {})
        assert counter["n"] == expected


# --- log 結構化 + 遮蔽(§9 測 4) ---

def test_log_carries_request_id_without_secrets(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="streamsight.api")
    make_client(json_handler(200, {})).request("GET", "http://test/records?secret=1")
    records = [r for r in caplog.records if r.name == "streamsight.api"]
    assert records
    assert getattr(records[0], "request_id", None)
    assert records[0].path == "/records"  # 去 query
    blob = " ".join(str(r.__dict__) for r in records)
    assert "Bearer" not in blob and "tok" not in blob and "secret" not in blob


def test_log_carries_elapsed_ms(caplog):
    """log extra 含 elapsed_ms（api-client.md §119）。"""
    import logging

    caplog.set_level(logging.INFO, logger="streamsight.api")
    make_client(json_handler(200, {})).request("GET", "http://test/records")
    records = [r for r in caplog.records if r.name == "streamsight.api"]
    assert records
    assert hasattr(records[0], "elapsed_ms"), "log record 應含 elapsed_ms 欄位"
    assert isinstance(records[0].elapsed_ms, (int, float)), "elapsed_ms 應為數值"


# --- ApiDataSource ↔ REST 端點對應(§9 測 7) ---

_RECORD_JSON = {
    "id": 1,
    "title": "溫度",
    "value": 25.5,
    "category": "感測器",
    "created_by": "alice",
    "created_at": "2026-07-18T00:00:00Z",
    "updated_at": "2026-07-18T01:00:00Z",
    "note": "",
    "deleted_at": None,
}


def make_ds(handler, **kw):
    return ApiDataSource(make_client(handler, **kw), "http://api")


def test_list_records_builds_query_params_and_parses_page():
    from lib.models import Page, Record

    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"items": [_RECORD_JSON], "total": 1, "page": 1, "size": 20})

    page = make_ds(handler).list_records(
        page=1, size=20, category="感測器", keyword="溫", sort="value:asc"
    )
    assert isinstance(page, Page) and page.total == 1
    assert isinstance(page.items[0], Record)
    url = captured["url"]
    assert "/records" in url
    for token in ("page=1", "size=20", "sort=value", "category=", "keyword="):
        assert token in url


def test_to_record_parses_iso8601_to_datetime():
    from datetime import datetime

    r = make_ds(json_handler(200, _RECORD_JSON)).get_record(1)
    assert isinstance(r.created_at, datetime)
    assert r.created_at.year == 2026 and r.updated_at.hour == 1


def test_create_record_posts_user_fields_only():
    captured = {}

    def handler(request):
        import json as _json

        captured["method"] = request.method
        captured["body"] = _json.loads(request.content)
        return httpx.Response(200, json=_RECORD_JSON)

    make_ds(handler).create_record(
        {"title": "溫度", "value": 25.5, "category": "感測器", "note": "n"},
        object(),
    )
    assert captured["method"] == "POST"
    assert set(captured["body"]) <= {"title", "value", "category", "note"}


def test_delete_record_issues_delete_and_returns_none():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        return httpx.Response(204)

    assert make_ds(handler).delete_record(1, object()) is None
    assert captured["method"] == "DELETE"


def test_bulk_create_parses_import_result():
    from lib.models import ImportResult

    payload = {"created": 2, "errors": [{"row_index": 3, "reason": "bad"}]}
    result = make_ds(json_handler(200, payload)).bulk_create([{}], object())
    assert isinstance(result, ImportResult)
    assert result.created == 2
    assert result.errors[0].row_index == 3 and result.errors[0].reason == "bad"
