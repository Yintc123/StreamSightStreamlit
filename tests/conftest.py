from __future__ import annotations

import pytest

# 與 lib/config.py 相關的環境變數：每個測試前一律清空，確保 hermetic（不被本機 shell / .env 汙染）。
_CONFIG_ENV_KEYS = [
    "APP_ENV", "APP_NAME", "APP_VERSION", "APP_COMMIT", "LOG_LEVEL",
    "USE_MOCK",
    "BFF_BASE_URL", "BFF_PUBLIC_BASE_URL", "BFF_SESSION_PATH", "BFF_LOGOUT_PATH", "BFF_LOGIN_PATH", "SESSION_COOKIE_NAME",
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
def _clear_analytics_caches():
    """清掉分析頁 st.cache_data 快取，避免跨測試互相污染（load/export 快取於篩選鍵）。"""
    try:
        import lib.data_source as ds_mod
        ds_mod.load_records_df.clear()
        ds_mod.build_export_bytes.clear()
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _isolate_config_env(monkeypatch):
    """每個測試前清掉設定相關 env 與 get_settings 快取，避免跨測試污染。

    設 APP_ENV=test 使 TestSettings 生效（env_file=None + use_mock=True），
    隔絕本機 .env（如 USE_MOCK=false）對測試的影響。
    """
    for key in _CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    _clear_settings_cache()
    yield
    _clear_settings_cache()
