from __future__ import annotations

import pytest

# 與 lib/config.py 相關的環境變數：每個測試前一律清空，確保 hermetic（不被本機 shell / .env 汙染）。
_CONFIG_ENV_KEYS = [
    "APP_ENV", "APP_NAME", "APP_VERSION", "APP_COMMIT", "LOG_LEVEL",
    "DATA_SOURCE", "AUTH_MODE",
    "BFF_BASE_URL", "BFF_SESSION_PATH", "BFF_LOGOUT_PATH", "BFF_LOGIN_PATH", "SESSION_COOKIE_NAME",
    "FASTAPI_BASE_URL",
    "HTTP_CONNECT_TIMEOUT_SECONDS", "HTTP_READ_TIMEOUT_SECONDS",
    "HTTP_RETRY_MAX", "HTTP_RETRY_BASE_SECONDS", "HTTP_RETRY_FACTOR",
    "REQUEST_ID_HEADER", "REQUEST_ID_PREFIX",
    "TOKEN_REFRESH_THRESHOLD_SECONDS", "INTROSPECTION_CACHE_TTL_SECONDS", "ROLE_ADMIN_VALUE",
]


def _clear_settings_cache() -> None:
    try:
        from lib.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _isolate_config_env(monkeypatch):
    """每個測試前清掉設定相關 env 與 get_settings 快取，避免跨測試污染。"""
    for key in _CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    _clear_settings_cache()
    yield
    _clear_settings_cache()
