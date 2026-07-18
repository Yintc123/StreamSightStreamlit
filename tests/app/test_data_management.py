from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib.models import Actor

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


def _open_data_management(actor: Actor) -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = actor
    at.run()
    at.switch_page("pages/data_management.py")
    at.run()
    return at


def test_lists_seed_data_with_row_action_buttons():
    at = _open_data_management(Actor("alice", "user"))
    assert not at.exception
    edit_buttons = [b for b in at.button if b.label == "編輯"]
    assert edit_buttons  # 列出種子資料的逐列動作


def test_non_creator_buttons_disabled_creator_enabled():
    """一般使用者 alice:自己建立的可編輯、他人的停用(不隱藏)。"""
    at = _open_data_management(Actor("alice", "user"))
    disabled_flags = [b.disabled for b in at.button if b.label == "編輯"]
    assert any(disabled_flags)  # 有他人資料 → 部分停用
    assert not all(disabled_flags)  # 有自己資料 → 部分可用


def test_admin_all_buttons_enabled():
    at = _open_data_management(Actor("admin", "admin"))
    edit_buttons = [b for b in at.button if b.label == "編輯"]
    assert edit_buttons
    assert all(not b.disabled for b in edit_buttons)


def _dev_switcher(at: AppTest):
    return next(s for s in at.selectbox if s.label == "目前使用者")


def test_dev_switcher_switches_user_and_updates_button_state():
    """DoD:切換 dev 使用者改變編輯/刪除按鈕停用狀態。"""
    at = AppTest.from_file(APP_PATH)
    at.run()  # mock 預設 alice
    at.switch_page("pages/data_management.py")
    at.run()
    alice_disabled = [b.disabled for b in at.button if b.label == "編輯"]
    assert any(alice_disabled)  # alice:部分他人資料停用

    _dev_switcher(at).set_value("Admin").run()
    admin_disabled = [b.disabled for b in at.button if b.label == "編輯"]
    assert admin_disabled  # 仍有列出資料
    assert not any(admin_disabled)  # admin:全部可編輯
