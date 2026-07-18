from __future__ import annotations

from types import SimpleNamespace

import pytest
import streamlit as st

from lib import auth
from lib.models import Actor, NotAuthenticated


@pytest.fixture
def fake_session(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(st, "session_state", store)
    return store


@pytest.fixture
def bff_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "bff")


def _set_cookies(monkeypatch, cookies: dict):
    monkeypatch.setattr(st, "context", SimpleNamespace(cookies=cookies))


_INTROSPECT_OK = {"user": {"name": "alice"}, "role": 1, "accessToken": "jwt", "expiresAt": 123}


# --- resolve_actor mock 分支(auth §8 測 1–2;APP_ENV 預設 local → AUTH_MODE=mock) ---

def test_resolve_actor_mock_defaults_alice_and_writes_back(fake_session):
    a = auth.resolve_actor()
    assert a == Actor("alice", "user")
    assert fake_session["actor"] == a  # 預設寫回 session


def test_resolve_actor_mock_returns_existing_actor(fake_session):
    fake_session["actor"] = Actor("admin", "admin")  # 如切換器選 admin
    assert auth.resolve_actor() == Actor("admin", "admin")


# --- get_access_token mock 分支(auth §8 測 3) ---

def test_get_access_token_mock_raises_runtime_error(fake_session):
    with pytest.raises(RuntimeError):
        auth.get_access_token()


def test_refresh_token_mock_raises_runtime_error(fake_session):
    with pytest.raises(RuntimeError):
        auth.refresh_token()


def test_raw_cookie_mock_raises_runtime_error(fake_session):
    with pytest.raises(RuntimeError):
        auth.raw_cookie()


# --- bff 分支(auth §8 測 4–9)---

def test_map_role_admin_user_and_unknown(bff_mode):
    assert auth.map_role(1) == "admin"
    assert auth.map_role(0) == "user"
    assert auth.map_role(99) == "user"


def test_resolve_actor_bff_no_cookie_returns_none_without_network(bff_mode, fake_session, monkeypatch):
    _set_cookies(monkeypatch, {})
    called = {"n": 0}
    monkeypatch.setattr(auth, "_introspect", lambda: called.__setitem__("n", 1))
    assert auth.resolve_actor() is None
    assert called["n"] == 0  # 無 cookie → 不打網路


def test_resolve_actor_bff_success_sets_actor_and_token(bff_mode, fake_session, monkeypatch):
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})
    monkeypatch.setattr(auth, "_introspect", lambda: _INTROSPECT_OK)
    actor = auth.resolve_actor()
    assert actor == Actor("alice", "admin")
    assert fake_session["access_token"] == "jwt"
    assert fake_session["token_expires_at"] == 123


def test_resolve_actor_bff_401_returns_none_and_clears(bff_mode, fake_session, monkeypatch):
    fake_session["access_token"] = "old"
    _set_cookies(monkeypatch, {"streamsight_session": "raw"})

    def boom():
        raise NotAuthenticated("session 失效")

    monkeypatch.setattr(auth, "_introspect", boom)
    assert auth.resolve_actor() is None
    assert "access_token" not in fake_session  # 清狀態


def test_refresh_token_bff_success_then_401(bff_mode, fake_session, monkeypatch):
    monkeypatch.setattr(
        auth,
        "_introspect",
        lambda: {"user": {"name": "a"}, "role": 0, "accessToken": "new", "expiresAt": 9},
    )
    assert auth.refresh_token() == "new"
    assert fake_session["access_token"] == "new"

    def boom():
        raise NotAuthenticated("x")

    monkeypatch.setattr(auth, "_introspect", boom)
    with pytest.raises(NotAuthenticated):
        auth.refresh_token()


def test_raw_cookie_bff_reads_context_cookie(bff_mode, fake_session, monkeypatch):
    _set_cookies(monkeypatch, {"streamsight_session": "rawval"})
    assert auth.raw_cookie() == "rawval"
    _set_cookies(monkeypatch, {})
    assert auth.raw_cookie() is None


def test_get_access_token_bff_returns_stored_token(bff_mode, fake_session):
    fake_session["access_token"] = "jwt"
    assert auth.get_access_token() == "jwt"
