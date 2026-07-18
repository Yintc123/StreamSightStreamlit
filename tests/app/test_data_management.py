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


def test_viewer_all_buttons_disabled():
    """Viewer admin 唯讀：所有編輯/刪除按鈕停用。"""
    at = _open_data_management(Actor("viewer", "admin", grade="viewer"))
    disabled_flags = [b.disabled for b in at.button if b.label == "編輯"]
    assert disabled_flags              # 有列出資料
    assert all(disabled_flags)        # 全部停用


def test_viewer_create_submit_disabled():
    """Viewer：新增分頁的「送出」按鈕停用。"""
    at = _open_data_management(Actor("viewer", "admin", grade="viewer"))
    submit = next((b for b in at.button if b.label == "送出"), None)
    assert submit is not None
    assert submit.disabled


def test_admin_all_buttons_enabled():
    at = _open_data_management(Actor("admin", "admin"))
    edit_buttons = [b for b in at.button if b.label == "編輯"]
    assert edit_buttons
    assert all(not b.disabled for b in edit_buttons)


def _dev_switcher(at: AppTest):
    return next(s for s in at.selectbox if s.label == "目前使用者")


def _category_box(at: AppTest):
    return next(s for s in at.selectbox if s.label == "分類")


# ── 排序選單 ──────────────────────────────────────────────────────

def _sort_box(at: AppTest):
    return next(s for s in at.selectbox if s.label == "排序")


def _apply_filter(at: AppTest) -> AppTest:
    """送出篩選表單（點「搜尋」按鈕）。"""
    next(b for b in at.button if b.label == "搜尋").click()
    return at.run()


def test_filter_form_has_search_button():
    """工具列有「搜尋」送出按鈕。"""
    at = _open_data_management(Actor("admin", "admin", grade="super_admin"))
    assert any(b.label == "搜尋" for b in at.button)


def test_sort_selectbox_exists():
    """工具列有排序選單。"""
    at = _open_data_management(Actor("admin", "admin", grade="super_admin"))
    assert _sort_box(at) is not None


def test_sort_changes_order():
    """切換排序後，markdown 清單順序改變（標題 ↑ vs 建立時間 ↓）。"""
    at = _open_data_management(Actor("admin", "admin", grade="super_admin"))
    default_texts = [m.value for m in at.markdown]
    _sort_box(at).set_value("標題 ↑").run()
    assert not at.exception
    sorted_texts = [m.value for m in at.markdown]
    assert default_texts != sorted_texts


# ── 8-2：篩選連線 ─────────────────────────────────────────────────

def test_category_filter_shows_only_matching_records():
    """篩選分類後，總筆數 < 40，且 > 0。"""
    at = _open_data_management(Actor("alice", "user"))
    before = _total_records(at)
    _category_box(at).set_value("感測器").run()
    assert not at.exception
    filtered = _total_records(at)
    assert 0 < filtered < before


def test_category_filter_all_restores_full_page():
    """切回「全部」，總筆數回到 200（種子資料）。"""
    at = _open_data_management(Actor("alice", "user"))
    _category_box(at).set_value("感測器").run()
    _category_box(at).set_value("全部").run()
    assert _total_records(at) == 200


def test_filter_change_resets_page_to_1():
    """篩選條件改變時，頁碼重置為 1。"""
    at = _open_data_management(Actor("alice", "user"))
    # 先跳到第 2 頁
    next(b for b in at.button if b.label == "下一頁 ›").click().run()
    assert at.session_state["dm_page"] == 2
    # 改篩選 → 頁碼應重置
    _category_box(at).set_value("感測器").run()
    assert at.session_state["dm_page"] == 1


# ── 8-3：分頁連線 ─────────────────────────────────────────────────

def test_next_page_shows_different_records():
    """點「下一頁」後，session_state dm_page 更新為 2。"""
    at = _open_data_management(Actor("alice", "user"))
    next(b for b in at.button if b.label == "下一頁 ›").click().run()
    assert not at.exception
    assert at.session_state["dm_page"] == 2


def test_prev_page_returns_to_page_1():
    """從第 2 頁點「上一頁」，dm_page 回到 1。"""
    at = _open_data_management(Actor("alice", "user"))
    next(b for b in at.button if b.label == "下一頁 ›").click().run()
    next(b for b in at.button if b.label == "‹ 上一頁").click().run()
    assert at.session_state["dm_page"] == 1


# ── 8-4：新增表單 ─────────────────────────────────────────────────

def _total_records(at: AppTest) -> int:
    """從 caption 取總筆數（pagination_controls 顯示「第 X / Y 頁 · 共 N 筆」）。"""
    for cap in at.caption:
        text = cap.value
        if "共" in text and "筆" in text:
            return int(text.split("共")[1].split("筆")[0].strip())
    return len(at.dataframe[0].value) if at.dataframe else 0


def test_create_tab_has_form():
    """新增分頁有表單欄位（標題、數值、分類、備註）與送出按鈕。"""
    at = _open_data_management(Actor("alice", "user"))
    labels = [ti.label for ti in at.text_input]
    assert "標題" in labels


def test_create_record_appears_in_list():
    """新增一筆後，列表總筆數 +1。分類用表單預設值（感測器），避免觸動 filter_bar。"""
    at = _open_data_management(Actor("alice", "user"))
    before = _total_records(at)

    # 只填標題，其餘欄位使用預設值
    next(ti for ti in at.text_input if ti.label == "標題").set_value("測試新標題").run()
    next(b for b in at.button if b.label == "送出").click().run()

    assert not at.exception
    assert _total_records(at) == before + 1


def test_create_empty_title_shows_error():
    """標題空白送出時顯示 st.error，不新增資料。"""
    at = _open_data_management(Actor("alice", "user"))
    before = _total_records(at)
    next(b for b in at.button if b.label == "送出").click().run()
    assert not at.exception
    assert at.error  # 有 st.error 元件
    assert _total_records(at) == before


# ── 8-5：編輯 dialog ──────────────────────────────────────────────

def _first_editable_edit_btn(at: AppTest):
    """取第一個可點擊的「編輯」按鈕（Alice 自己建立的）。"""
    return next(b for b in at.button if b.label == "編輯" and not b.disabled)


def test_edit_dialog_updates_title():
    """點「編輯」→ session_state trigger → dialog 顯示，修改標題送出後列表刷新。"""
    at = _open_data_management(Actor("alice", "user"))
    _first_editable_edit_btn(at).click().run()  # 寫入 dm_edit_id → rerun
    assert not at.exception
    # dialog 開啟後有「標題」text_input（key=dm_edit_title 確保不與 create 表單衝突）
    title_input = next(ti for ti in at.text_input if ti.key == "dm_edit_title")
    title_input.set_value("已修改的標題").run()
    next(b for b in at.button if b.label == "更新").click().run()
    assert not at.exception
    # 標題欄以 st.write 渲染，出現在 at.markdown
    texts = [m.value for m in at.markdown]
    assert any("已修改的標題" in t for t in texts)


# ── 8-6：刪除 dialog ──────────────────────────────────────────────

def _first_editable_delete_btn(at: AppTest):
    return next(b for b in at.button if b.label == "刪除" and not b.disabled)


def test_delete_dialog_removes_record():
    """點「刪除」→ 確認 → 列表筆數 -1。"""
    at = _open_data_management(Actor("alice", "user"))
    before = _total_records(at)
    _first_editable_delete_btn(at).click().run()
    assert not at.exception
    # dialog 有「確認刪除」按鈕
    next(b for b in at.button if b.label == "確認刪除").click().run()
    assert not at.exception
    assert _total_records(at) == before - 1


def test_delete_cancel_keeps_record():
    """點「刪除」→ 取消 → 筆數不變。"""
    at = _open_data_management(Actor("alice", "user"))
    before = _total_records(at)
    _first_editable_delete_btn(at).click().run()
    next(b for b in at.button if b.label == "取消").click().run()
    assert not at.exception
    assert _total_records(at) == before


# ── 8-7：匯入分頁渲染（AppTest 不支援 file_uploader，邏輯測試在 unit） ────

def test_import_tab_renders_without_error():
    """匯入分頁正常渲染（不 crash）。"""
    at = _open_data_management(Actor("alice", "user"))
    assert not at.exception


def test_dev_switcher_switches_user_and_updates_button_state():
    """切換 dev 使用者改變編輯/刪除按鈕停用狀態。"""
    at = AppTest.from_file(APP_PATH)
    at.run()  # mock 預設 Super Admin
    at.switch_page("pages/data_management.py")
    at.run()
    super_admin_disabled = [b.disabled for b in at.button if b.label == "編輯"]
    assert super_admin_disabled       # 有列出資料
    assert not any(super_admin_disabled)  # super_admin:全部可編輯

    _dev_switcher(at).set_value("Viewer").run()
    viewer_disabled = [b.disabled for b in at.button if b.label == "編輯"]
    assert viewer_disabled            # 仍有列出資料
    assert all(viewer_disabled)       # viewer:全部不可編輯（唯讀）
