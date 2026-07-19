"""StreamSight 進入點:薄排版 + 委派 lib/(見 docs/specs/app-skeleton.md §3)。

每次 rerun 依固定順序執行:頁面設定 → 載入 CSS → 身分解析(gate)→ 依 role 動態組頁 → 路由。
註:結構化 logging(§3 步驟 ②′ init_logging)於接 API 階段(request_id 模組)補上。
"""
import streamlit as st

from lib.auth import resolve_actor
from lib.config import get_settings
from lib.models import NotAuthenticated
from lib.nav import build_pages, render_dev_switcher
from lib.request_id import init_logging
from lib.state import clear_auth
from lib.theme import load_css
from lib.topbar import render_topbar

st.set_page_config(
    page_title="StreamSight",
    layout="wide",
    initial_sidebar_state="expanded",
)  # ① 頁面設定(必須最先)
load_css()  # ② 載入一次 CSS
init_logging()  # ②′ 結構化 log 管線（冪等，掛 request-id filter）

actor = resolve_actor()  # ③ 身分解析(mock/bff 單一出口)

if actor is None:  # ④ 未登入(僅 AUTH_MODE=bff 會發生)→ 跳轉 Next.js 登入頁
    _s = get_settings()
    _login_url = f"{_s.bff_base_url}{_s.bff_login_path}"
    st.markdown(
        f'<meta http-equiv="refresh" content="0; url={_login_url}">',
        unsafe_allow_html=True,
    )
    st.stop()

if get_settings().auth_mode == "mock":  # ⑤ 開發切換器(僅 mock)
    actor = render_dev_switcher(actor)

_s2 = get_settings()
_cms_url = f"{_s2.bff_base_url}/cms" if _s2.auth_mode == "bff" else ""
render_topbar(actor, cms_base_url=_cms_url)  # ⑥ 自訂頂列（全模式）

try:
    pages = build_pages(actor)  # ⑦ 依 actor.grade 動態組頁清單(見 §5)
    st.navigation(pages).run()  # ⑧ 交給 Streamlit 路由
except NotAuthenticated:
    # session 失效(401×2)：清狀態 + 重導登入（error-handling §3、auth §5）
    clear_auth()
    _s = get_settings()
    _login_url = f"{_s.bff_base_url}{_s.bff_login_path}"
    st.markdown(
        f'<meta http-equiv="refresh" content="0; url={_login_url}">',
        unsafe_allow_html=True,
    )
    st.stop()
