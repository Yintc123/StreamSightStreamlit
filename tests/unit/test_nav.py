from __future__ import annotations

from collections import namedtuple

import pytest
import streamlit as st

from lib import nav
from lib.models import Actor, AdminRole

# 以假 Page 捕捉 build_pages 傳入的 (path, title, url_path, default),避免 bare 模式下 st.Page 的限制。
FakePage = namedtuple("FakePage", ["path", "title", "url_path", "default"])


@pytest.fixture
def capture_pages(monkeypatch):
    def fake_page(path, title=None, url_path=None, default=False):
        return FakePage(path, title, url_path, default)

    monkeypatch.setattr(st, "Page", fake_page)


# --- build_pages 依 actor.grade 動態註冊(app-skeleton §5) ---

def test_super_admin_has_system_management_page(capture_pages):
    actor = Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)
    pages = nav.build_pages(actor)
    titles = [p.title for p in pages]
    assert "系統管理" in titles
    assert len(pages) == 4


def test_root_has_system_management_page(capture_pages):
    """ROOT（grade=999）亦應看到系統管理頁（>= SUPER_ADMIN=100）。"""
    actor = Actor("root", "admin", grade=AdminRole.ROOT)
    pages = nav.build_pages(actor)
    assert "系統管理" in [p.title for p in pages]


def test_editor_has_no_system_management_page(capture_pages):
    actor = Actor("editor", "admin", grade=AdminRole.EDITOR)
    pages = nav.build_pages(actor)
    titles = [p.title for p in pages]
    assert "系統管理" not in titles
    assert len(pages) == 3


def test_viewer_has_no_system_management_page(capture_pages):
    actor = Actor("viewer", "admin", grade=AdminRole.VIEWER)
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
    actor = Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)
    titles = [p.title for p in nav.build_pages(actor)]
    assert "儀表板" not in titles


def test_default_page_is_data_management(capture_pages):
    """預設頁為資料管理：Streamlit 以 default=True 頁承接根路徑 / 與 404 fallback。"""
    actor = Actor("viewer", "admin", grade=AdminRole.VIEWER)
    pages = nav.build_pages(actor)
    defaults = [p for p in pages if p.default]
    assert len(defaults) == 1
    assert defaults[0].title == "資料管理"


def test_data_management_page_has_url_path(capture_pages):
    """資料管理頁 URL 路徑明確固定為 /data_management（不靠檔名推導），且為預設頁。"""
    actor = Actor("viewer", "admin", grade=AdminRole.VIEWER)
    dm = next(p for p in nav.build_pages(actor) if p.title == "資料管理")
    assert dm.url_path == "data_management"
    # 同時為預設頁：/ 與 404 亦 fallback 至此
    assert dm.default is True


# --- 頁面順序與路徑（frontend-pages.md 頁面一覽 / 檔案結構） ---

def test_page_titles_and_order_super_admin(capture_pages):
    """super_admin 頁清單標題與順序嚴格符合規格（frontend-pages.md 頁面一覽）。"""
    actor = Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)
    titles = [p.title for p in nav.build_pages(actor)]
    assert titles == ["資料管理", "即時監控", "資料分析", "系統管理"]


def test_page_titles_and_order_non_super_admin(capture_pages):
    """editor/viewer 頁清單標題與順序嚴格符合規格（無系統管理）。"""
    actor = Actor("editor", "admin", grade=AdminRole.EDITOR)
    titles = [p.title for p in nav.build_pages(actor)]
    assert titles == ["資料管理", "即時監控", "資料分析"]


def test_page_file_paths(capture_pages):
    """page 檔案路徑對齊規格書（frontend-pages.md §檔案結構）。"""
    actor = Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN)
    paths = [p.path for p in nav.build_pages(actor)]
    assert paths == [
        "pages/data_management.py",
        "pages/realtime_monitor.py",
        "pages/analytics.py",
        "pages/system_management.py",
    ]


def test_analytics_page_has_url_path(capture_pages):
    """資料分析頁 URL 路徑固定為 /analytics（frontend-pages.md 頁面一覽）。"""
    actor = Actor("viewer", "admin", grade=AdminRole.VIEWER)
    analytics = next(p for p in nav.build_pages(actor) if p.title == "資料分析")
    assert analytics.url_path == "analytics"
    # 不再是預設頁：/ 與 404 fallback 改由資料管理承接
    assert analytics.default is False


# --- render_dev_switcher 純邏輯（app-skeleton §3⑤ / CLAUDE.md lib/ 需有 unit test） ---

def test_dev_actor_options_cover_all_grades():
    """_DEV_ACTORS 覆蓋四種 grade（int）：ROOT=999 / SUPER_ADMIN=100 / EDITOR=50 / VIEWER=0。"""
    grades = [a.grade for _, a in nav._DEV_ACTORS]
    assert grades == [AdminRole.ROOT, AdminRole.SUPER_ADMIN, AdminRole.EDITOR, AdminRole.VIEWER]


def test_dev_actor_count_is_four():
    """開發切換器正好有 4 個使用者選項（Root / Super Admin / Editor / Viewer）。"""
    assert len(nav._DEV_ACTORS) == 4


def test_dev_actor_usernames_are_unique():
    """各 dev actor username 唯一，確保 render_dev_switcher 的當前選項查找不衝突。"""
    usernames = [a.username for _, a in nav._DEV_ACTORS]
    assert len(usernames) == len(set(usernames))
