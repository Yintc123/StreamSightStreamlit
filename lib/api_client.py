"""API Client:對外 HTTP 層(BFF introspection + FastAPI 業務 API)。

見規格 docs/specs/api-client.md。本階段先提供傳輸層例外 ApiError(§3.1);
_request 骨幹、ApiDataSource、重試等於接 API 階段補上。
"""
from __future__ import annotations

from typing import Optional


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
