"""TopBar：對齊 StreamSightFrontend CmsTopBar（h-12 bg-surface-card border-b border-line px-4）。

品牌 + 系統切換 Nav（管理後台 / 資料平台）+ 右側（username、ThemeToggle icon、登出）。
ThemeToggle 由 ENABLE_THEME_TOGGLE 控制：關閉時 icon 不渲染；開啟時渲染可互動按鈕，
切換由 client-side JS 完成（theme-toggle.md §6.2）。
"""
from __future__ import annotations

import html as _html

import streamlit as st

from lib.models import Actor

_SUN_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="5"/>'
    '<line x1="12" y1="1" x2="12" y2="3"/>'
    '<line x1="12" y1="21" x2="12" y2="23"/>'
    '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>'
    '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>'
    '<line x1="1" y1="12" x2="3" y2="12"/>'
    '<line x1="21" y1="12" x2="23" y2="12"/>'
    '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>'
    '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'
    '</svg>'
)

_MOON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'
    '</svg>'
)


def _build_topbar_html(
    actor: Actor,
    cms_base_url: str = "",
    theme: str = "light",
    enable_theme_toggle: bool = False,
) -> str:
    """純函式：產生 TopBar HTML 字串（不依賴 Streamlit，可單元測試）。"""
    cms_href = cms_base_url if cms_base_url else "#"
    username = _html.escape(actor.username) if actor else ""
    # 初始伺服器渲染以 light 為預設猜測（icon＝太陽、aria-pressed=true）；
    # 真正的 live 主題由 client-side JS 依 cookie 於載入時校正（theme-toggle.md §6.2.4）。
    is_light = theme == "light"
    icon = _SUN_SVG if is_light else _MOON_SVG
    theme_btn = (
        f'<button class="ss-topbar__theme-btn" type="button" '
        f'aria-pressed="{"true" if is_light else "false"}" '
        f'aria-label="{"切換為深色" if is_light else "切換為淺色"}">{icon}</button>'
        if enable_theme_toggle
        else ""
    )

    return (
        '<div class="ss-topbar">'
        f'<a class="ss-topbar__brand" href="{cms_href}" target="_self">Stream'
        f'<span class="ss-topbar__accent">Sight</span></a>'
        '<nav class="ss-topbar__nav">'
        f'<a class="ss-topbar__sysitem" href="{cms_href}" target="_self">管理後台</a>'
        '<span class="ss-topbar__sysitem ss-topbar__sysitem--active">資料平台</span>'
        "</nav>"
        '<div class="ss-topbar__right">'
        f'<span class="ss-topbar__username">{username}</span>'
        f"{theme_btn}"
        # onclick 在 st.markdown 的 react-markdown 管線中靜默失效，登出走 <a href="?logout=1">
        # 由 app.py 偵測 query param 執行 auth.logout()（logout.md §2）
        '<a class="ss-topbar__logout ss-topbar__sysitem" href="?logout=1" target="_self">登出</a>'
        "</div>"
        "</div>"
    )


def render_topbar(
    actor: Actor,
    cms_base_url: str = "",
    theme: str = "light",
    enable_theme_toggle: bool = False,
) -> None:
    """TopBar 注入頁面頂端（position:fixed；CSS 佔位補償見 styles/main.css）。"""
    st.markdown(
        _build_topbar_html(actor, cms_base_url, theme, enable_theme_toggle),
        unsafe_allow_html=True,
    )
