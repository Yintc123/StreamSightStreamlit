"""StreamSight 進入點:薄排版 + 委派 lib/(見 docs/specs/app-skeleton.md §3)。

每次 rerun 依固定順序執行:頁面設定 → 載入 CSS → 身分解析(gate)→ 依 role 動態組頁 → 路由。
註:結構化 logging(§3 步驟 ②′ init_logging)於接 API 階段(request_id 模組)補上。
"""
import streamlit as st

from lib.auth import resolve_actor
from lib.config import get_settings
from lib.nav import build_pages, render_dev_switcher
from lib.theme import load_css

st.set_page_config(
    page_title="StreamSight",
    layout="wide",
    initial_sidebar_state="expanded",
)  # ① 頁面設定(必須最先)
load_css()  # ② 載入一次 CSS

actor = resolve_actor()  # ③ 身分解析(mock/bff 單一出口)

if actor is None:  # ④ 未登入(僅 AUTH_MODE=bff 會發生)→ 只註冊導向頁
    st.navigation([st.Page("pages/gate.py", title="登入")]).run()
    st.stop()

if get_settings().auth_mode == "mock":  # ⑤ 開發切換器(僅 mock)
    actor = render_dev_switcher(actor)

pages = build_pages(actor.role)  # ⑥ 依 role 動態組頁清單
st.navigation(pages).run()  # ⑦ 交給 Streamlit 路由
