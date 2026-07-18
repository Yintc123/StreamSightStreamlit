"""API Client:對外 HTTP 層(FastAPI 業務 API + BFF introspection)。

見規格 docs/specs/api-client.md。內容:
- ApiError(§3.1):傳輸層例外。
- ApiClient(§4、§5):_request 骨幹,附 X-Request-ID、逾時、log、狀態→例外映射、
  401 reactive refresh、GET 網路重試(sleep 可注入)、bearer/cookie 認證。
- ApiDataSource + _to_record(§6、§7):實作 DataSource、REST 端點對應、JSON→Record。
BFF introspection 呼叫(auth="cookie")由 lib/auth.py 於 bff cycle 使用。
"""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from typing import Any, Callable, Optional

import httpx

from lib.models import (
    DEFAULT_SORT,
    ImportResult,
    NotAuthenticated,
    Page,
    PermissionDenied,
    Record,
    RecordNotFound,
    RowError,
    ValidationError,
)
from lib.request_id import (
    LOGGER_NAME,
    get_current,
    new_request_id,
    set_current,
    with_request_id,
)

_logger = logging.getLogger(LOGGER_NAME)


class ApiError(Exception):
    """傳輸層例外:逾時 / 連線錯誤 / 5xx / 非預期狀態 / 後端契約破壞。

    一律帶 request_id 供三端 log 對照;status 於逾時 / 連線錯誤為 None(§3.1)。
    """

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        request_id: Optional[str] = None,
        code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.request_id = request_id
        self.code = code


_IDEMPOTENT = {"GET", "HEAD", "OPTIONS"}
_RETRYABLE_STATUS = {502, 503, 504}


class ApiClient:
    """對外 HTTP 骨幹:附 X-Request-ID、逾時、log、錯誤轉譯、認證方式。

    auth 接縫(get_token/refresh_token/raw_cookie)由 lib/auth.py 提供,本層只消費。
    client 可注入(測試以 httpx.MockTransport),sleep 可注入(網路重試不真的等待)。
    """

    def __init__(
        self,
        *,
        client: httpx.Client,
        get_token: Optional[Callable[[], str]] = None,
        refresh_token: Optional[Callable[[], str]] = None,
        raw_cookie: Optional[Callable[[], Optional[str]]] = None,
        cookie_name: str = "streamsight_session",
        timeout: Optional[Any] = None,
        retry_max: int = 2,
        retry_base: float = 0.2,
        retry_factor: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._get_token = get_token
        self._refresh_token = refresh_token
        self._raw_cookie = raw_cookie
        self._cookie_name = cookie_name
        self._timeout = timeout
        self._retry_max = retry_max
        self._retry_base = retry_base
        self._retry_factor = retry_factor
        self._sleep = sleep

    def request(
        self,
        method: str,
        url: str,
        *,
        auth: str = "bearer",
        json: Optional[Any] = None,
        params: Optional[dict] = None,
    ) -> Any:
        headers: dict = {}
        if json is not None:
            headers["Content-Type"] = "application/json"
        if auth == "bearer":
            headers["Authorization"] = f"Bearer {self._get_token()}"
        elif auth == "cookie":
            headers["Cookie"] = f"{self._cookie_name}={self._raw_cookie()}"

        idempotent = method.upper() in _IDEMPOTENT
        attempts = 0
        refreshed = False
        while True:
            try:
                resp, rid = self._send(method, url, headers, json, params)
            except ApiError:
                # 網路錯誤(逾時 / 連線):僅冪等方法重試
                if idempotent and attempts < self._retry_max:
                    self._sleep(self._backoff(attempts))
                    attempts += 1
                    continue
                raise
            status = resp.status_code
            # 401:僅 bearer 做一次 reactive refresh 後重試原請求
            if status == 401 and auth == "bearer" and not refreshed:
                headers["Authorization"] = f"Bearer {self._refresh_token()}"
                refreshed = True
                continue
            # 5xx 網路類:僅冪等方法重試
            if status in _RETRYABLE_STATUS and idempotent and attempts < self._retry_max:
                self._sleep(self._backoff(attempts))
                attempts += 1
                continue
            return self._handle(resp, rid)

    def _send(self, method, url, headers, json, params):
        rid = new_request_id()
        set_current(rid)
        sent = with_request_id(headers, rid)
        try:
            kwargs: dict = {"headers": sent, "params": params}
            if json is not None:
                kwargs["json"] = json
            if self._timeout is not None:
                kwargs["timeout"] = self._timeout
            resp = self._client.request(method, url, **kwargs)
            self._log(rid, method, url, resp.status_code)
            return resp, rid
        except httpx.TimeoutException as exc:
            raise ApiError("請求逾時", status=None, request_id=rid) from exc
        except httpx.TransportError as exc:
            raise ApiError("連線失敗", status=None, request_id=rid) from exc
        finally:
            set_current(None)

    def _handle(self, resp: httpx.Response, rid: str) -> Any:
        status = resp.status_code
        if status == 204:
            return None
        if 200 <= status < 300:
            return resp.json() if resp.content else None
        message = self._error_message(resp)
        if status in (400, 422):
            raise ValidationError(message)
        if status == 403:
            raise PermissionDenied(message)
        if status == 404:
            raise RecordNotFound(message)
        if status == 401:
            raise NotAuthenticated(message)
        raise ApiError(message, status=status, request_id=rid)

    @staticmethod
    def _error_message(resp: httpx.Response) -> str:
        try:
            body = resp.json()
        except Exception:
            return f"HTTP {resp.status_code}"
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            return body["error"].get("message") or f"HTTP {resp.status_code}"
        return f"HTTP {resp.status_code}"

    def _backoff(self, attempt: int) -> float:
        # 指數退避 + ±50% 抖動;sleep 可注入,測試不真的等待
        base = self._retry_base * (self._retry_factor ** attempt)
        return base * random.uniform(0.5, 1.5)

    def _log(self, rid: str, method: str, url: str, status: int) -> None:
        # 只記 method / path(去 query)/ status / rid;絕不記 token / cookie / body
        path = httpx.URL(url).path
        level = (
            logging.INFO
            if status < 400
            else logging.WARNING
            if status < 500
            else logging.ERROR
        )
        _logger.log(
            level,
            "api_call",
            extra={"request_id": rid, "method": method, "path": path, "status": status},
        )


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    # Python 3.9 的 fromisoformat 不吃 'Z',先正規化為 +00:00
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_record(data: dict) -> Record:
    """後端 JSON → Record;缺欄位 / 型別不符視為契約破壞 → ApiError。"""
    try:
        return Record(
            id=data["id"],
            title=data["title"],
            value=float(data["value"]),
            category=data["category"],
            created_by=data["created_by"],
            created_at=_parse_dt(data["created_at"]),
            updated_at=_parse_dt(data["updated_at"]),
            note=data.get("note", ""),
            deleted_at=_parse_dt(data.get("deleted_at")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(
            "系統資料異常(後端契約破壞)", status=None, request_id=get_current()
        ) from exc


class ApiDataSource:
    """實作 DataSource 介面,呼叫 FastAPI 業務 API(§6 端點對應)。"""

    def __init__(self, client: ApiClient, base_url: str) -> None:
        self._c = client
        self._base = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    def list_records(
        self,
        page: int = 1,
        size: int = 20,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        sort: str = DEFAULT_SORT,
        include_deleted: bool = False,
    ) -> Page:
        params: dict = {"page": page, "size": size, "sort": sort}
        if category:
            params["category"] = category
        if keyword:
            params["keyword"] = keyword
        if include_deleted:
            params["include_deleted"] = "true"
        data = self._c.request("GET", self._url("/records"), params=params)
        return Page(
            items=[_to_record(item) for item in data["items"]],
            total=data["total"],
            page=data["page"],
            size=data["size"],
        )

    def get_record(self, record_id: int) -> Record:
        return _to_record(self._c.request("GET", self._url(f"/records/{record_id}")))

    def create_record(self, data: dict, actor: Any) -> Record:
        return _to_record(
            self._c.request("POST", self._url("/records"), json=_user_fields(data))
        )

    def update_record(self, record_id: int, data: dict, actor: Any) -> Record:
        return _to_record(
            self._c.request(
                "PATCH", self._url(f"/records/{record_id}"), json=_user_fields(data)
            )
        )

    def delete_record(self, record_id: int, actor: Any) -> None:
        self._c.request("DELETE", self._url(f"/records/{record_id}"))

    def bulk_create(self, rows: list, actor: Any) -> ImportResult:
        data = self._c.request("POST", self._url("/records/bulk"), json={"rows": rows})
        return ImportResult(
            created=data["created"],
            errors=[
                RowError(row_index=e["row_index"], reason=e["reason"])
                for e in data.get("errors", [])
            ],
        )


def _user_fields(data: dict) -> dict:
    # 僅送使用者可填欄位;id / created_by / 時間戳由後端管理
    return {
        "title": data.get("title"),
        "value": data.get("value"),
        "category": data.get("category"),
        "note": data.get("note", ""),
    }
