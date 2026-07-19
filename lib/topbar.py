"""TopBar：對齊 StreamSightFrontend CmsTopBar（h-12 bg-surface-card border-b border-line px-4）。

品牌 + 系統切換 Nav（管理後台 / 資料平台）+ 右側（username、ThemeToggle 開關、登出）。
ThemeToggle 採 role=switch 開關模式：OFF = light（白天），ON = dark（夜間）。
"""
from __future__ import annotations

import html as _html

import streamlit as st

from lib.models import Actor

# ThemeToggle 開關 thumb（純 CSS 定位，不含 SVG）
_THEME_SWITCH = (
    '<button class="ss-topbar__theme-switch" type="button" role="switch" '
    '{aria_checked} aria-label="深色模式">'
    '<span class="ss-topbar__theme-switch-thumb"></span>'
    '</button>'
)


def _build_topbar_html(actor: Actor, cms_base_url: str = "", theme: str = "light") -> str:
    """純函式：產生 TopBar HTML 字串（不依賴 Streamlit，可單元測試）。"""
    cms_href = cms_base_url if cms_base_url else "#"
    username = _html.escape(actor.username) if actor else ""
    aria_checked = 'aria-checked="true"' if theme == "dark" else 'aria-checked="false"'
    theme_switch = _THEME_SWITCH.format(aria_checked=aria_checked)

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
        f"{theme_switch}"
        '<button class="ss-topbar__sysitem" type="button">登出</button>'
        "</div>"
        "</div>"
    )


def render_topbar(actor: Actor, cms_base_url: str = "", theme: str = "light") -> None:
    """TopBar 注入頁面頂端（position:fixed；CSS 佔位補償見 styles/main.css）。

    使用 st.markdown(unsafe_allow_html=True) 以便 AppTest 可驗證渲染結果。
    HTML 內容完全自行產生，username 已 html.escape()，不存在 XSS 風險。
    theme 由呼叫端傳入 st.session_state['theme']（見 docs/specs/theme-toggle.md §8）。
    """
    st.markdown(_build_topbar_html(actor, cms_base_url, theme), unsafe_allow_html=True)
