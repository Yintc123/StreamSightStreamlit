"""Request ID 模組:跨服務關聯 ID(X-Request-ID)。

見規格 docs/specs/request-id.md。純函式為主,ID 當前值以 ContextVar 環境傳遞,
供 logging filter 自動帶上。全 mock 模式下休眠(無對外呼叫)。
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Callable, Mapping, Optional

HEADER = "X-Request-ID"  # 預設;實際名稱可由 config 覆寫(§2)
LOGGER_NAME = "streamsight.api"

_current: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def new_request_id(prefix: str = "st", gen: Callable[[], uuid.UUID] = uuid.uuid4) -> str:
    """產生關聯 ID,格式 '<prefix>-<uuid4 hex>';gen 可注入以利測試決定性。"""
    return f"{prefix}-{gen().hex}"


def with_request_id(headers: Mapping, request_id: str, header: str = HEADER) -> dict:
    """回傳附上關聯 ID 的新 headers(不就地修改)。
    若已含該 header(大小寫不敏感)→ 沿用既有值、不覆寫。"""
    out = dict(headers)
    if any(k.lower() == header.lower() for k in out):
        return out  # 沿用上游 ID,避免斷鏈
    out[header] = request_id
    return out


def read_request_id(response_headers: Mapping, header: str = HEADER) -> Optional[str]:
    """從 headers 以大小寫不敏感方式取回關聯 ID;無則 None。"""
    target = header.lower()
    for key, value in response_headers.items():
        if key.lower() == target:
            return value
    return None


def set_current(request_id: Optional[str]) -> None:
    """設定當前請求 ID 到 ContextVar(供 logging filter 讀取)。"""
    _current.set(request_id)


def get_current() -> Optional[str]:
    """取當前請求 ID;無則 None。"""
    return _current.get()


class _RequestIdFilter(logging.Filter):
    _streamsight = True

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_current()
        return True


def init_logging() -> None:
    """冪等:把讀 get_current() 的 filter 掛到 'streamsight.api' logger。
    由 app.py 啟動時呼叫一次;重複呼叫不重複掛(app-skeleton §3 步驟 ②′)。"""
    logger = logging.getLogger(LOGGER_NAME)
    if any(getattr(f, "_streamsight", False) for f in logger.filters):
        return
    logger.addFilter(_RequestIdFilter())
