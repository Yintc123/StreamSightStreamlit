"""StreamSight 進入點:薄排版 + 委派 lib/(見 docs/specs/app-skeleton.md §3)。

每次 rerun 依固定順序執行:頁面設定 → 載入 CSS → 身分解析(gate)→ 依 role 動態組頁 → 路由。
註:結構化 logging(§3 步驟 ②′ init_logging)於接 API 階段(request_id 模組)補上。
"""
import streamlit as st

from lib import idle
from lib.auth import logout, resolve_actor
from lib.config import AppEnv, get_settings
from lib.models import NotAuthenticated
from lib.nav import build_pages, render_dev_switcher
from lib.request_id import init_logging
from lib.sidebar import inject_sidebar_sync_js
from lib.state import clear_auth, pop_logout_reason, set_logout_reason
from lib.theme import inject_theme_js, init_theme_state, load_css
from lib.topbar import render_topbar
from lib.ui import page_shell

st.set_page_config(
    page_title="StreamSight",
    layout="wide",
    initial_sidebar_state="expanded",
)  # ① 頁面設定(必須最先)
load_css()          # ② 載入一次 CSS
init_theme_state()  # ②′ 主題 session_state 初始化（light 預設，見 theme-toggle.md §5.1）
init_logging()      # ②″ 結構化 log 管線（冪等，掛 request-id filter）

actor = resolve_actor()  # ③ 身分解析(mock/bff 單一出口)

if actor is None:  # ④ 未登入(僅 AUTH_MODE=bff 會發生)→ 跳轉 Next.js 登入頁
    # 重導 / TopBar 連結一律用 bff_public_base_url 組 URL(瀏覽器可達);
    # bff_base_url 只給 server-side BFF 呼叫(docker 下為內部主機名)。
    _login_url = get_settings().bff_login_url
    st.markdown(
        f'<meta http-equiv="refresh" content="0; url={_login_url}">',
        unsafe_allow_html=True,
    )
    st.stop()

# ④″ 閒置登出原因提示(只顯示一次;須在 actor 解析後、登出偵測前,見 idle-timeout §7.1)
if pop_logout_reason() == "idle":
    st.toast("因閒置逾 15 分鐘，已登出", icon="⏱️")

# ④′ 登出偵測(TopBar <a href="?logout=1">;閒置計時器另帶 reason=idle;必須在 resolve_actor
#     之後,確保 bff 模式 CSRF token 已寫入 session_state,見 logout.md §3、idle-timeout §5)
if st.query_params.get("logout") == "1":
    reason = idle.parse_logout_reason(st.query_params.get("reason"))  # 白名單(僅顯示)
    logout()  # mock 清狀態;bff POST BFF logout + 清狀態(try/finally 最佳努力)
    _s = get_settings()
    if _s.use_mock:
        if reason == "idle":
            set_logout_reason("idle")  # 跨 rerun 存活,下一輪顯示 toast(idle-timeout §6.2)
        st.query_params.clear()  # mock 無登入頁:清 param 後 rerun 以預設角色重進
        st.rerun()
    else:
        _login_url = _s.bff_login_url
        if reason == "idle":
            # 閒置:過場頁顯示原因 + 延時 3s 跳轉,讓訊息可見(idle-timeout §6.1)
            st.info("因閒置逾 15 分鐘，已將您登出，正在導向登入頁…")
            st.markdown(
                f'<meta http-equiv="refresh" content="3; url={_login_url}">',
                unsafe_allow_html=True,
            )
        else:
            # 手動登出:即時跳轉(不受閒置規格拖慢)
            st.markdown(
                f'<meta http-equiv="refresh" content="0; url={_login_url}">',
                unsafe_allow_html=True,
            )
        st.stop()

if get_settings().use_mock:  # ⑤ 開發切換器(僅 mock)
    actor = render_dev_switcher(actor)

_cms_url = get_settings().bff_cms_url
_enable_toggle = get_settings().enable_theme_toggle
_is_prod = get_settings().app_env == AppEnv.PRODUCTION
render_topbar(  # ⑥ 自訂頂列
    actor,
    cms_base_url=_cms_url,
    theme=st.session_state["theme"],
    enable_theme_toggle=_enable_toggle,
)
inject_theme_js(enable_theme_toggle=_enable_toggle, is_prod=_is_prod)  # ⑦ ThemeToggle JS（冪等）
idle.inject_idle_js()  # ⑦′ 注入閒置計時器 JS（冪等；純 client-side 偵測滑鼠/鍵盤）
inject_sidebar_sync_js(  # ⑦″ 側欄寬度 cookie 橋接（kill-switch；sidebar-width-sync.md §3.4）
    enabled=get_settings().enable_sidebar_width_sync, is_prod=_is_prod
)

try:
    pages = build_pages(actor)  # ⑦ 依 actor.grade 動態組頁清單(見 §5)
    nav = st.navigation(pages)
    # ⑧ 路由：以當前頁 title 為 key 包一層穩定容器，讓每頁有唯一 element 身分，
    #    切頁時整塊 remount 取代而非同位置重用，消除跨頁殘影（見 ui.md page_shell）。
    with page_shell(nav.title):
        nav.run()
except NotAuthenticated:
    # session 失效(401×2)：清狀態 + 重導登入（error-handling §3、auth §5）
    clear_auth()
    _login_url = get_settings().bff_login_url
    st.markdown(
        f'<meta http-equiv="refresh" content="0; url={_login_url}">',
        unsafe_allow_html=True,
    )
    st.stop()
