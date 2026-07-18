"""樣式載入:於進入點載入一次共用 CSS。

見規格 docs/specs/design-system.md。主題優先(config.toml),CSS 最小化。
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st


def load_css(path: str = "styles/main.css") -> None:
    """讀取外部 CSS 並以 <style> 注入;每次 rerun 重注入無副作用。"""
    css = Path(path).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
