from __future__ import annotations

import pytest

from lib.config import AppEnv, get_settings


# --- 行為 1 + 2:環境選類 + 各環境預設矩陣(config §1、§4) ---

def test_default_env_is_local_all_mock():
    """無 APP_ENV → 預設 local,DATA_SOURCE / AUTH_MODE 皆 mock(§4 矩陣)。"""
    s = get_settings()
    assert s.app_env == AppEnv.LOCAL
    assert s.data_source == "mock"
    assert s.auth_mode == "mock"


def test_development_defaults_api_bff(monkeypatch):
    """development 預設 api / bff(§4)。"""
    monkeypatch.setenv("APP_ENV", "development")
    s = get_settings()
    assert s.data_source == "api"
    assert s.auth_mode == "bff"


# --- 行為 7:小寫正規化(§1) ---

def test_app_env_lowercased(monkeypatch):
    monkeypatch.setenv("APP_ENV", "LOCAL")
    assert get_settings().app_env == AppEnv.LOCAL


# --- 行為 1:未知 APP_ENV → ValueError 並列出合法值(§5.1) ---

def test_unknown_app_env_raises_listing_valid(monkeypatch):
    monkeypatch.setenv("APP_ENV", "bogus")
    with pytest.raises(ValueError) as exc:
        get_settings()
    msg = str(exc.value)
    for valid in ["local", "development", "stage", "production", "test"]:
        assert valid in msg


# --- 行為 3:個別旗標可覆寫環境預設(§2、§3) ---

def test_flag_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")  # 預設 mock/mock
    monkeypatch.setenv("AUTH_MODE", "bff")  # 覆寫為 bff(mock+bff 為合法組合)
    s = get_settings()
    assert s.data_source == "mock"
    assert s.auth_mode == "bff"


# --- 行為 4:無效組合守衛 api+mock → 啟動即拋錯(§2、§5.2) ---

def test_invalid_combo_api_mock_raises(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DATA_SOURCE", "api")
    monkeypatch.setenv("AUTH_MODE", "mock")
    with pytest.raises(ValueError):
        get_settings()


# --- 行為 6/7:空字串視為未設,套環境預設(§5.6) ---

def test_empty_string_treated_as_unset(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")  # 預設 api/bff
    monkeypatch.setenv("DATA_SOURCE", "")  # 空 → 套 development 預設 api
    s = get_settings()
    assert s.data_source == "api"


# --- 行為 5:production 守衛(§5.3–5.4) ---

def test_production_valid_config_ok(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BFF_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("FASTAPI_BASE_URL", "https://api.example.com")
    s = get_settings()
    assert s.data_source == "api"
    assert s.auth_mode == "bff"


def test_production_rejects_localhost(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BFF_BASE_URL", "http://localhost:3000")
    monkeypatch.setenv("FASTAPI_BASE_URL", "http://localhost:3001")
    with pytest.raises(ValueError):
        get_settings()


def test_production_rejects_non_https(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BFF_BASE_URL", "http://app.example.com")
    monkeypatch.setenv("FASTAPI_BASE_URL", "http://api.example.com")
    with pytest.raises(ValueError):
        get_settings()


def test_production_rejects_mock(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BFF_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("FASTAPI_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("DATA_SOURCE", "mock")
    monkeypatch.setenv("AUTH_MODE", "mock")
    with pytest.raises(ValueError):
        get_settings()


# --- 行為 6:test 環境 hermetic,忽略 .env(§5.5) ---

def test_local_env_reads_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("AUTH_MODE=bff\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "local")
    assert get_settings().auth_mode == "bff"  # local 讀 .env


def test_test_env_is_hermetic_ignores_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("AUTH_MODE=bff\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "test")
    assert get_settings().auth_mode == "mock"  # test 忽略 .env,套預設 mock


# --- HTTP / cookie 設定項(config §3.3、§3.5) ---

def test_http_and_cookie_setting_defaults():
    s = get_settings()
    assert s.session_cookie_name == "streamsight_session"
    assert s.http_connect_timeout_seconds == 3
    assert s.http_read_timeout_seconds == 10
    assert s.http_retry_max == 2
    assert s.http_retry_base_seconds == 0.2
    assert s.http_retry_factor == 2


# --- BFF / 認證設定項(config §3.3、§3.7) ---

def test_bff_auth_setting_defaults():
    s = get_settings()
    assert s.bff_session_path == "/api/auth/session"
    assert s.bff_logout_path == "/api/auth/logout"
    assert s.role_admin_value == 1


def test_bff_login_path_default():
    """bff_login_path 預設 /login，供 actor is None 時跳轉 Next.js 登入頁。"""
    s = get_settings()
    assert s.bff_login_path == "/login"


def test_bff_cms_path_default():
    """bff_cms_path 預設 /cms（TopBar 品牌 & 管理後台連結目標；見 topbar-cms-link.md §2.1）。"""
    s = get_settings()
    assert s.bff_cms_path == "/cms"


# --- streamlit_origin / bff_csrf_path(config §3.3;015 §7.1B) ---

def test_streamlit_origin_default():
    """streamlit_origin 預設 http://localhost:8501，供 logout Origin header 使用(S6)。"""
    s = get_settings()
    assert s.streamlit_origin == "http://localhost:8501"


def test_bff_csrf_path_removed():
    """bff_csrf_path 已移除；csrfToken 改由 introspection 一併回傳(S7)。"""
    s = get_settings()
    assert not hasattr(s, "bff_csrf_path")


# --- App meta 欄位(config §3.1) ---

def test_app_meta_defaults():
    """APP_NAME / APP_VERSION / APP_COMMIT 三個 meta 欄位有預設值(config §3.1)。"""
    s = get_settings()
    assert s.app_name == "StreamSight"
    assert s.app_version == "0.0.0"
    assert s.app_commit == ""


# --- LOG_LEVEL 各環境預設(config §3.1、§4) ---

def test_log_level_local_is_debug():
    """local 環境 LOG_LEVEL 預設 DEBUG(config §4 矩陣)。"""
    s = get_settings()
    assert s.log_level == "DEBUG"


def test_log_level_development_is_debug(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    s = get_settings()
    assert s.log_level == "DEBUG"


def test_log_level_stage_is_info(monkeypatch):
    monkeypatch.setenv("APP_ENV", "stage")
    monkeypatch.setenv("BFF_BASE_URL", "https://stage.example.com")
    monkeypatch.setenv("FASTAPI_BASE_URL", "https://stage-api.example.com")
    s = get_settings()
    assert s.log_level == "INFO"


def test_log_level_test_is_warning(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    s = get_settings()
    assert s.log_level == "WARNING"


# --- Request ID 設定項(config §3.6) ---

def test_request_id_config_defaults():
    """REQUEST_ID_HEADER / REQUEST_ID_PREFIX 有預設值(config §3.6)。"""
    s = get_settings()
    assert s.request_id_header == "X-Request-ID"
    assert s.request_id_prefix == "st"


# --- Token / introspection 設定項(config §3.7) ---

def test_token_auth_config_defaults():
    """TOKEN_REFRESH_THRESHOLD_SECONDS / INTROSPECTION_CACHE_TTL_SECONDS 有預設值(config §3.7)。"""
    s = get_settings()
    assert s.token_refresh_threshold_seconds == 60
    assert s.introspection_cache_ttl_seconds == 30
