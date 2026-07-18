from __future__ import annotations

import pytest
import streamlit as st

from lib import auth
from lib.models import Actor


@pytest.fixture
def fake_session(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(st, "session_state", store)
    return store


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
