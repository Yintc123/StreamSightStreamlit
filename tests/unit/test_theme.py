from __future__ import annotations

import streamlit as st

from lib import theme


def test_load_css_injects_style_tag(monkeypatch, tmp_path):
    css = tmp_path / "x.css"
    css.write_text(".a{color:red}", encoding="utf-8")

    calls: dict = {}

    def fake_markdown(body, **kwargs):
        calls["body"] = body
        calls["kwargs"] = kwargs

    monkeypatch.setattr(st, "markdown", fake_markdown)

    theme.load_css(str(css))

    assert "<style>" in calls["body"]
    assert ".a{color:red}" in calls["body"]
    assert calls["kwargs"].get("unsafe_allow_html") is True
