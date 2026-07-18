"""設定模組:執行環境模型(APP_ENV)與設定項。

見規格 docs/specs/config.md。鏡像後端 AppEnv:BaseSettings + 每環境子類覆寫預設
+ get_settings() 依 APP_ENV 選類並 lru_cache。
"""
from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGE = "stage"
    PRODUCTION = "production"
    TEST = "test"


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,  # KEY= 空字串視為未設,套預設(§5.6)
    )

    app_env: AppEnv = AppEnv.LOCAL
    data_source: str = "mock"
    auth_mode: str = "mock"

    # BFF(introspection 目標)/ FastAPI(業務 API 目標)base URL(§3.3、§3.4)
    bff_base_url: str = "http://localhost:3000"
    fastapi_base_url: str = "http://localhost:3001"
    session_cookie_name: str = "streamsight_session"  # 必與前端一致
    bff_session_path: str = "/api/auth/session"  # introspection 端點
    bff_logout_path: str = "/api/auth/logout"
    bff_login_path: str = "/login"  # Next.js 登入頁路徑(actor is None 時跳轉)
    streamlit_origin: str = "http://localhost:8501"  # logout Origin header(015 §7.1B)
    role_admin_value: int = 1  # role 數值 → admin,其餘 user;待與前端 Role enum 對齊

    # HTTP client(§3.5;時間單位一律「秒」)
    http_connect_timeout_seconds: float = 3
    http_read_timeout_seconds: float = 10
    http_retry_max: int = 2  # 網路重試上限(僅 GET)
    http_retry_base_seconds: float = 0.2
    http_retry_factor: float = 2

    @model_validator(mode="after")
    def _check_prod_guards(self) -> "BaseAppSettings":
        # §5.3:stage / production 的 base URL 必須 HTTPS 且非 localhost。
        if self.app_env in (AppEnv.STAGE, AppEnv.PRODUCTION):
            for name, url in (
                ("BFF_BASE_URL", self.bff_base_url),
                ("FASTAPI_BASE_URL", self.fastapi_base_url),
            ):
                if not url.startswith("https://"):
                    raise ValueError(f"{self.app_env.value} 需 HTTPS:{name}={url!r}")
                if "localhost" in url or "127.0.0.1" in url:
                    raise ValueError(f"{self.app_env.value} 不可用 localhost:{name}={url!r}")
        # §5.4:production 禁 mock。
        if self.app_env == AppEnv.PRODUCTION and (
            self.data_source == "mock" or self.auth_mode == "mock"
        ):
            raise ValueError("production 禁用 mock(DATA_SOURCE / AUTH_MODE 皆須非 mock)")
        return self

    @model_validator(mode="after")
    def _check_flag_combo(self) -> "BaseAppSettings":
        # 硬性守衛(§5.2):DATA_SOURCE=api 必須搭 AUTH_MODE=bff。
        # api+mock 無 token → 業務 API 必 401,故啟動即拒絕。
        if self.data_source == "api" and self.auth_mode == "mock":
            raise ValueError(
                "無效組合:DATA_SOURCE=api 需搭 AUTH_MODE=bff(業務 API 需 JWT);"
                "api+mock 為無效組合"
            )
        return self


class LocalSettings(BaseAppSettings):
    """開發者本機:全 mock。"""


class DevelopmentSettings(BaseAppSettings):
    data_source: str = "api"
    auth_mode: str = "bff"


class StageSettings(DevelopmentSettings):
    """預備環境:近正式守衛(後續 cycle 補)。"""


class ProductionSettings(StageSettings):
    """正式:強制 HTTPS / 非 localhost / 禁 mock(後續 cycle 補)。"""


class TestSettings(BaseAppSettings):
    """pytest 專用:hermetic,忽略 .env。"""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )


_ENV_MAP = {
    AppEnv.LOCAL: LocalSettings,
    AppEnv.DEVELOPMENT: DevelopmentSettings,
    AppEnv.STAGE: StageSettings,
    AppEnv.PRODUCTION: ProductionSettings,
    AppEnv.TEST: TestSettings,
}


def _resolve_app_env() -> AppEnv:
    """讀 APP_ENV、小寫正規化;未知值 → ValueError 並列出合法值(§5.1)。"""
    raw = os.getenv("APP_ENV", "local").lower()
    try:
        return AppEnv(raw)
    except ValueError:
        valid = ", ".join(e.value for e in AppEnv)
        raise ValueError(f"未知的 APP_ENV: {raw!r};合法值為: {valid}") from None


@lru_cache
def get_settings() -> BaseAppSettings:
    """依 APP_ENV 選對應設定類並實例化(lru_cache)。"""
    env = _resolve_app_env()
    return _ENV_MAP[env](app_env=env)
