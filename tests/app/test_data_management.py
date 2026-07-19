from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib.api_client import ApiError
from lib.models import Actor, AdminRole

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
    at = _open_data_management(Actor("viewer", "admin", grade=AdminRole.VIEWER))
    disabled_flags = [b.disabled for b in at.button if b.label == "編輯"]
    assert disabled_flags              # 有列出資料
    assert all(disabled_flags)        # 全部停用


def test_viewer_create_submit_disabled():
    """Viewer：新增分頁的「送出」按鈕停用。"""
    at = _open_data_management(Actor("viewer", "admin", grade=AdminRole.VIEWER))
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
    at = _open_data_management(Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN))
    assert any(b.label == "搜尋" for b in at.button)


def test_sort_selectbox_exists():
    """工具列有排序選單。"""
    at = _open_data_management(Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN))
    assert _sort_box(at) is not None


def test_sort_changes_order():
    """切換排序後，markdown 清單順序改變（標題 ↑ vs 建立時間 ↓）。"""
    at = _open_data_management(Actor("admin", "admin", grade=AdminRole.SUPER_ADMIN))
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
    _first_editable_edit_btn(at).click().run()  # 寫入 dm_edit_id → rerun → trigger pop → dialog 開啟
    assert not at.exception
    # dialog 開啟後有「標題」text_input（key=dm_edit_title 確保不與 create 表單衝突）
    title_input = next(ti for ti in at.text_input if ti.key == "dm_edit_title")
    # AppTest 的每次 .run() 都是 full page rerun（無 fragment rerun），
    # pop() 後 dm_edit_id 已清除，需在 submit 前手動 re-arm。
    # （real Streamlit：dialog 作為 fragment 保持開啟，不需 re-arm）
    title_input.set_value("已修改的標題")  # 僅設值，不 run
    at.session_state["dm_edit_id"] = 1  # re-arm：種子第 1 筆為 alice 所建
    next(b for b in at.button if b.label == "更新").click().run()
    assert not at.exception
    # 標題欄以 st.write 渲染，出現在 at.markdown
    texts = [m.value for m in at.markdown]
    assert any("已修改的標題" in t for t in texts)


def test_edit_dialog_does_not_reopen_on_subsequent_rerun():
    """開啟 dialog 後再次 rerun（無互動）不應重開 dialog（regression：dm_edit_id 未清除）。"""
    at = _open_data_management(Actor("alice", "user"))
    _first_editable_edit_btn(at).click().run()
    assert not at.exception
    assert any(ti.key == "dm_edit_title" for ti in at.text_input), "dialog 應已開啟"

    # 不送出，直接再 rerun（模擬點其他按鈕後觸發的 rerun）
    at.run()
    assert not at.exception
    assert not any(ti.key == "dm_edit_title" for ti in at.text_input), \
        "dialog 不應在下一次 rerun 後重新開啟"


# ── 8-6：刪除 dialog ──────────────────────────────────────────────

def _first_editable_delete_btn(at: AppTest):
    return next(b for b in at.button if b.label == "刪除" and not b.disabled)


def test_delete_dialog_removes_record():
    """點「刪除」→ 確認 → 列表筆數 -1。"""
    at = _open_data_management(Actor("alice", "user"))
    before = _total_records(at)
    _first_editable_delete_btn(at).click().run()
    assert not at.exception
    # dialog 有「確認刪除」按鈕；AppTest 需 re-arm 使下次 run 重開 dialog
    at.session_state["dm_delete_id"] = 1  # 種子第 1 筆為 alice 所建
    next(b for b in at.button if b.label == "確認刪除").click().run()
    assert not at.exception
    assert _total_records(at) == before - 1


def test_delete_cancel_keeps_record():
    """點「刪除」→ 取消 → 筆數不變。"""
    at = _open_data_management(Actor("alice", "user"))
    before = _total_records(at)
    _first_editable_delete_btn(at).click().run()
    at.session_state["dm_delete_id"] = 1  # re-arm
    next(b for b in at.button if b.label == "取消").click().run()
    assert not at.exception
    assert _total_records(at) == before


# ── 8-7：匯入分頁渲染（AppTest 不支援 file_uploader，邏輯測試在 unit） ────

def test_import_tab_renders_without_error():
    """匯入分頁正常渲染（不 crash）。"""
    at = _open_data_management(Actor("alice", "user"))
    assert not at.exception


def test_list_records_api_error_shows_error_not_crash(monkeypatch):
    """list_records 失敗時頁面顯示 st.error，不 crash（03-data-management §錯誤處理）。"""
    from lib import data_source as _ds_mod

    class _FailDS:
        def list_records(self, **kw):
            raise ApiError("連線逾時", status=None, request_id="st-fail1")

        def get_record(self, *a, **kw): ...
        def create_record(self, *a, **kw): ...
        def update_record(self, *a, **kw): ...
        def delete_record(self, *a, **kw): ...
        def bulk_create(self, *a, **kw): ...

    monkeypatch.setattr(_ds_mod, "get_data_source", lambda: _FailDS())

    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = Actor("alice", "admin", grade=AdminRole.EDITOR)
    at.run()
    at.switch_page("pages/data_management.py")
    at.run()

    assert not at.exception
    assert at.error


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


# ── 匯入執行：session trigger（dm_import_rows）+ flash（dm_import_result） ────
# AppTest 不支援 file_uploader，改以 trigger key 直接驅動匯入執行路徑。

class _StubDS:
    """可注入行為的假 DataSource（僅實作本組測試用到的方法）。"""

    def __init__(self, bulk_result=None, bulk_exc=None):
        self._bulk_result = bulk_result
        self._bulk_exc = bulk_exc

    def list_records(self, **kw):
        from lib.models import Page
        return Page(items=[], total=0, page=1, size=20)

    def bulk_create(self, rows, actor):
        if self._bulk_exc is not None:
            raise self._bulk_exc
        return self._bulk_result


def _open_dm_with_ds(monkeypatch, ds, actor=None) -> AppTest:
    from lib import data_source as _ds_mod

    monkeypatch.setattr(_ds_mod, "get_data_source", lambda: ds)
    at = AppTest.from_file(APP_PATH)
    at.session_state["actor"] = actor or Actor("alice", "admin", grade=AdminRole.EDITOR)
    at.run()
    at.switch_page("pages/data_management.py")
    at.run()
    return at


def test_import_bulk_create_api_error_shows_error_not_crash(monkeypatch):
    """bulk_create 拋 ApiError → render_error（st.error）呈現，不 crash、不 rerun。"""
    ds = _StubDS(bulk_exc=ApiError("連線逾時", status=None, request_id="imp-1"))
    at = _open_dm_with_ds(monkeypatch, ds)
    at.session_state["dm_import_rows"] = [{"title": "X", "value": 1, "category": "感測器"}]
    at.run()
    assert not at.exception
    assert at.error


def test_import_success_message_survives_rerun(monkeypatch):
    """匯入成功 → rerun 刷新列表後，成功訊息仍顯示（flash pattern，不被 rerun 沖掉）。"""
    from lib.models import ImportResult

    ds = _StubDS(bulk_result=ImportResult(created=3, errors=[]))
    at = _open_dm_with_ds(monkeypatch, ds)
    at.session_state["dm_import_rows"] = [{"title": "X", "value": 1, "category": "感測器"}]
    at.run()
    assert not at.exception
    assert any("3" in s.value for s in at.success)


def test_import_partial_errors_show_warning_with_row_numbers(monkeypatch):
    """部分錯誤 → warning + 錯誤列號（1-based）標示，訊息同樣不被 rerun 沖掉。"""
    from lib.models import ImportResult, RowError

    ds = _StubDS(bulk_result=ImportResult(
        created=1, errors=[RowError(row_index=2, reason="bad")],
    ))
    at = _open_dm_with_ds(monkeypatch, ds)
    at.session_state["dm_import_rows"] = [{"title": "X", "value": 1, "category": "感測器"}]
    at.run()
    assert not at.exception
    assert any("1" in w.value for w in at.warning)
    captions = [c.value for c in at.caption]
    assert any("3" in c for c in captions)   # row_index=2 → 列號 3


# ── 寫入路徑錯誤處理：所有 ds.* 失敗一律 render_error，不 crash ────────────

def _seed_record():
    from datetime import datetime, timezone

    from lib.models import Record
    _now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return Record(id=1, title="種子", value=1.0, category="感測器",
                  created_by="alice", created_at=_now, updated_at=_now)


class _WriteFailDS(_StubDS):
    """寫入操作可注入例外的假 DataSource。"""

    def __init__(self, get_exc=None, create_exc=None, update_exc=None, delete_exc=None):
        super().__init__()
        self._excs = {"get": get_exc, "create": create_exc,
                      "update": update_exc, "delete": delete_exc}

    def list_records(self, **kw):
        from lib.models import Page
        return Page(items=[_seed_record()], total=1, page=1, size=20)

    def _maybe_raise(self, op):
        if self._excs[op] is not None:
            raise self._excs[op]

    def get_record(self, rid):
        self._maybe_raise("get")
        return _seed_record()

    def create_record(self, data, actor):
        self._maybe_raise("create")
        return _seed_record()

    def update_record(self, rid, data, actor):
        self._maybe_raise("update")
        return _seed_record()

    def delete_record(self, rid, actor):
        self._maybe_raise("delete")


def test_create_api_error_shows_error_not_crash(monkeypatch):
    """create_record 拋 ApiError → render_error（st.error），不 crash。"""
    ds = _WriteFailDS(create_exc=ApiError("連線逾時", status=None, request_id="c-1"))
    at = _open_dm_with_ds(monkeypatch, ds)
    title_input = next(t for t in at.text_input if t.label == "標題")
    title_input.set_value("X")
    next(b for b in at.button if b.label == "送出").click()
    at.run()
    assert not at.exception
    assert at.error


def test_update_api_error_shows_error_not_crash(monkeypatch):
    """update_record 拋 ApiError → dialog 內 render_error，不 crash。"""
    ds = _WriteFailDS(update_exc=ApiError("連線逾時", status=None, request_id="u-1"))
    at = _open_dm_with_ds(monkeypatch, ds)
    at.session_state["dm_edit_id"] = 1
    at.run()
    at.session_state["dm_edit_id"] = 1   # re-arm（AppTest 無 fragment rerun）
    next(b for b in at.button if b.label == "更新").click()
    at.run()
    assert not at.exception
    assert at.error


def test_delete_api_error_shows_error_not_crash(monkeypatch):
    """delete_record 拋 ApiError → dialog 內 render_error，不 crash。"""
    ds = _WriteFailDS(delete_exc=ApiError("連線逾時", status=None, request_id="d-1"))
    at = _open_dm_with_ds(monkeypatch, ds)
    at.session_state["dm_delete_id"] = 1
    at.run()
    at.session_state["dm_delete_id"] = 1   # re-arm
    next(b for b in at.button if b.label == "確認刪除").click()
    at.run()
    assert not at.exception
    assert at.error


def test_dialog_get_record_api_error_shows_error_not_crash(monkeypatch):
    """dialog 載入 get_record 拋 ApiError → render_error + 可關閉，不 crash。"""
    ds = _WriteFailDS(get_exc=ApiError("連線逾時", status=None, request_id="g-1"))
    at = _open_dm_with_ds(monkeypatch, ds)
    at.session_state["dm_edit_id"] = 1
    at.run()
    assert not at.exception
    assert at.error
