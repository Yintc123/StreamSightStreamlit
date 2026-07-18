from __future__ import annotations

from collections import namedtuple

import pytest
import streamlit as st

from lib import nav
from lib.models import Actor

# 以假 Page 捕捉 build_pages 傳入的 (path, title, default),避免 bare 模式下 st.Page 的限制。
FakePage = namedtuple("FakePage", ["path", "title", "default"])


@pytest.fixture
def capture_pages(monkeypatch):
    def fake_page(path, title=None, default=False):
        return FakePage(path, title, default)

    monkeypatch.setattr(st, "Page", fake_page)


# --- build_pages 依 actor.grade 動態註冊(app-skeleton §5) ---

def test_super_admin_has_system_management_page(capture_pages):
    actor = Actor("admin", "admin", grade="super_admin")
    pages = nav.build_pages(actor)
    titles = [p.title for p in pages]
    assert "系統管理" in titles
    assert len(pages) == 4


def test_editor_has_no_system_management_page(capture_pages):
    actor = Actor("editor", "admin", grade="editor")
    pages = nav.build_pages(actor)
    titles = [p.title for p in pages]
    assert "系統管理" not in titles
    assert len(pages) == 3


def test_viewer_has_no_system_management_page(capture_pages):
    actor = Actor("viewer", "admin", grade="viewer")
    pages = nav.build_pages(actor)
    titles = [p.title for p in pages]
    assert "系統管理" not in titles
    assert len(pages) == 3


def test_non_admin_role_has_no_system_management_page(capture_pages):
    # latent 防線：role != "admin" 亦不可見（本部署不會觸發，保留深度防禦）
    actor = Actor("user", "user", grade=None)
    pages = nav.build_pages(actor)
    titles = [p.title for p in pages]
    assert "系統管理" not in titles


def test_dashboard_page_removed(capture_pages):
    actor = Actor("admin", "admin", grade="super_admin")
    titles = [p.title for p in nav.build_pages(actor)]
    assert "儀表板" not in titles


def test_default_page_is_analytics(capture_pages):
    actor = Actor("viewer", "admin", grade="viewer")
    pages = nav.build_pages(actor)
    defaults = [p for p in pages if p.default]
    assert len(defaults) == 1
    assert defaults[0].title == "資料分析"
