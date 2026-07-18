from __future__ import annotations

from collections import namedtuple

import pytest
import streamlit as st

from lib import nav

# 以假 Page 捕捉 build_pages 傳入的 (path, title, default),避免 bare 模式下 st.Page 的限制。
FakePage = namedtuple("FakePage", ["path", "title", "default"])


@pytest.fixture
def capture_pages(monkeypatch):
    def fake_page(path, title=None, default=False):
        return FakePage(path, title, default)

    monkeypatch.setattr(st, "Page", fake_page)


# --- build_pages 依 role 動態註冊(app-skeleton §5、§9) ---

def test_user_has_no_admin_page(capture_pages):
    pages = nav.build_pages("user")
    titles = [p.title for p in pages]
    assert "系統管理" not in titles
    assert len(pages) == 3


def test_admin_has_admin_page(capture_pages):
    pages = nav.build_pages("admin")
    titles = [p.title for p in pages]
    assert "系統管理" in titles
    assert len(pages) == 4


def test_dashboard_page_removed(capture_pages):
    titles = [p.title for p in nav.build_pages("admin")]
    assert "儀表板" not in titles


def test_default_page_is_analytics(capture_pages):
    pages = nav.build_pages("user")
    defaults = [p for p in pages if p.default]
    assert len(defaults) == 1
    assert defaults[0].title == "資料分析"
