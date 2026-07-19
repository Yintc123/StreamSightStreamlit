from __future__ import annotations

import pytest
import streamlit as st

from lib import state
from lib.models import Actor


@pytest.fixture
def fake_session(monkeypatch):
    """以純 dict 取代 st.session_state,讓 state helper 可在無 Streamlit runtime 下測試。"""
    store: dict = {}
    monkeypatch.setattr(st, "session_state", store)
    return store


# --- actor ---

def test_get_actor_none_when_unset(fake_session):
    assert state.get_actor() is None


def test_set_and_get_actor(fake_session):
    a = Actor("alice", "user")
    state.set_actor(a)
    assert state.get_actor() == a
    assert fake_session["actor"] == a


# --- token ---

def test_get_token_none_when_unset(fake_session):
    assert state.get_token() is None


def test_set_token_writes_token_and_expiry(fake_session):
    state.set_token("jwt-abc", 999)
    assert state.get_token() == "jwt-abc"
    assert fake_session["access_token"] == "jwt-abc"
    assert fake_session["token_expires_at"] == 999


# --- last_request_id ---

def test_set_last_request_id(fake_session):
    state.set_last_request_id("st-abc")
    assert fake_session["last_request_id"] == "st-abc"


# --- csrf_token (S1-S3) ---

def test_get_csrf_none_when_unset(fake_session):
    assert state.get_csrf() is None


def test_set_and_get_csrf(fake_session):
    state.set_csrf("tok")
    assert state.get_csrf() == "tok"
    assert fake_session["csrf_token"] == "tok"


# --- clear_auth ---

def test_clear_auth_removes_actor_and_token(fake_session):
    state.set_actor(Actor("alice", "user"))
    state.set_token("jwt", 123)
    state.clear_auth()
    assert state.get_actor() is None
    assert state.get_token() is None


def test_clear_auth_removes_csrf_token(fake_session):
    state.set_csrf("tok")
    state.clear_auth()
    assert state.get_csrf() is None
    assert "csrf_token" not in fake_session

# --- logout_reason（idle-timeout §6.2、§7.1；不列入 clear_auth） ---

def test_logout_reason_none_when_unset(fake_session):
    assert state.pop_logout_reason() is None


def test_set_then_pop_logout_reason(fake_session):
    state.set_logout_reason("idle")
    assert state.pop_logout_reason() == "idle"
    # pop 後即清，只顯示一次
    assert state.pop_logout_reason() is None


def test_clear_auth_does_not_clear_logout_reason(fake_session):
    """登出原因需跨 clear_auth/rerun 存活，供下一輪顯示提示。"""
    state.set_logout_reason("idle")
    state.clear_auth()
    assert state.pop_logout_reason() == "idle"
