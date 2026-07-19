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

    # App meta(§3.1)
    app_name: str = "StreamSight"
    app_version: str = "0.0.0"
    app_commit: str = ""
    log_level: str = "DEBUG"  # 各環境子類覆寫;大寫(§3.1、§4)

    use_mock: bool = True  # True → mock data + mock auth；False → api + bff（對齊前端 USE_MOCK）
    enable_theme_toggle: bool = False  # True → 顯示主題切換 icon；False → 隱藏（0/1）
    enable_sidebar_width_sync: bool = False  # True → 側欄寬度 cookie 橋接；kill-switch（0/1）

    # BFF(introspection 目標)/ FastAPI(業務 API 目標)base URL(§3.3、§3.4)
    bff_base_url: str = "http://localhost:3000"
    # 瀏覽器可達的 BFF base URL:登入重導 meta refresh 與 TopBar 連結用。
    # docker compose 下 bff_base_url 是內部主機名(http://frontend:3000),
    # 瀏覽器解析不了;此值須設為對外位址(如 http://localhost:3000)。
    # 未設(空)→ 回退 bff_base_url(本機開發兩者相同)。
    bff_public_base_url: str = ""
    fastapi_base_url: str = "http://localhost:3001"
    session_cookie_name: str = "streamsight_session"  # 必與前端一致
    bff_session_path: str = "/api/auth/session"  # introspection 端點
    bff_logout_path: str = "/api/auth/logout"
    bff_login_path: str = "/login"  # Next.js 登入頁路徑(actor is None 時跳轉)
    bff_cms_path: str = "/cms"  # CMS 根路徑;TopBar 品牌 & 管理後台連結目標
    streamlit_origin: str = "http://localhost:8501"  # logout Origin header(015 §7.1B)
    role_admin_value: int = 1  # role 數值 → admin,其餘 user;待與前端 Role enum 對齊

    # HTTP client(§3.5;時間單位一律「秒」)
    http_connect_timeout_seconds: float = 3
    http_read_timeout_seconds: float = 10
    http_retry_max: int = 2  # 網路重試上限(僅 GET)
    http_retry_base_seconds: float = 0.2
    http_retry_factor: float = 2

    # Request ID(§3.6)
    request_id_header: str = "X-Request-ID"
    request_id_prefix: str = "st"

    # 認證 / token(§3.7)
    token_refresh_threshold_seconds: int = 60
    introspection_cache_ttl_seconds: int = 30

    # 閒置逾時(§3.8;idle-timeout §7、§8;純前端 JS 偵測滑鼠/鍵盤)
    idle_timeout_seconds: int = 900  # 連續無活動達此秒數 → 自動登出(15 分)
    idle_activity_throttle_seconds: int = 30  # 活動事件節流,避免 mousemove 高頻洗版

    @property
    def bff_login_url(self) -> str:
        """瀏覽器要跳轉的登入頁完整 URL(public base + login path)。"""
        return f"{self.bff_public_base_url}{self.bff_login_path}"

    @property
    def bff_cms_url(self) -> str:
        """TopBar 品牌 / 管理後台連結目標(public base + cms path)。"""
        return f"{self.bff_public_base_url}{self.bff_cms_path}"

    @property
    def fastapi_ws_url(self) -> str:
        """http(s) → ws(s)；先換 https，再換 http，避免 https 雙重替換。"""
        return (
            self.fastapi_base_url
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        )

    @model_validator(mode="after")
    def _fill_public_base_url(self) -> "BaseAppSettings":
        # bff_public_base_url 未設 → 回退 bff_base_url(本機開發兩者相同)。
        if not self.bff_public_base_url:
            self.bff_public_base_url = self.bff_base_url
        return self

    @model_validator(mode="after")
    def _check_prod_guards(self) -> "BaseAppSettings":
        # §5.3:stage / production 的 base URL 必須 HTTPS 且非 localhost。
        if self.app_env in (AppEnv.STAGE, AppEnv.PRODUCTION):
            for name, url in (
                ("BFF_BASE_URL", self.bff_base_url),
                ("BFF_PUBLIC_BASE_URL", self.bff_public_base_url),
                ("FASTAPI_BASE_URL", self.fastapi_base_url),
            ):
                if not url.startswith("https://"):
                    raise ValueError(f"{self.app_env.value} 需 HTTPS:{name}={url!r}")
                if "localhost" in url or "127.0.0.1" in url:
                    raise ValueError(f"{self.app_env.value} 不可用 localhost:{name}={url!r}")
        # §5.4:production 禁 mock。
        if self.app_env == AppEnv.PRODUCTION and self.use_mock:
            raise ValueError("production 禁用 mock(USE_MOCK 必須為 false/0)")
        return self


class LocalSettings(BaseAppSettings):
    """開發者本機:全 mock。"""


class DevelopmentSettings(BaseAppSettings):
    use_mock: bool = False


class StageSettings(DevelopmentSettings):
    """預備環境:近正式守衛(後續 cycle 補)。"""

    log_level: str = "INFO"


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

    log_level: str = "WARNING"


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
