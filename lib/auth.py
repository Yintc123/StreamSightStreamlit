"""Auth 模組:身分單一出口 resolve_actor,以及對 api_client 的 token 接縫。

見規格 docs/specs/auth.md、docs/specs/auth-flow.md。
本階段實作 mock 分支(骨架);bff 分支於接 API 階段補上(auth §8 測 4–9)。
"""
from __future__ import annotations

from typing import Optional

from lib import state
from lib.config import get_settings
from lib.models import Actor

# mock 種子預設身分(auth §3;供開發切換器覆寫)
_DEFAULT_MOCK_ACTOR = Actor("alice", "user")


def resolve_actor() -> Optional[Actor]:
    """身分單一出口:吸收 mock / bff 差異,app.py 只看回傳值。"""
    settings = get_settings()
    if settings.auth_mode == "mock":
        actor = state.get_actor()
        if actor is None:
            actor = Actor(_DEFAULT_MOCK_ACTOR.username, _DEFAULT_MOCK_ACTOR.role)
            state.set_actor(actor)
        return actor
    raise NotImplementedError("AUTH_MODE=bff 尚未實作(接 API 階段)")


def get_access_token() -> str:
    """供 api_client 帶 Bearer;mock 下無 token,誤呼即拋錯凸顯設定錯誤(auth §2)。"""
    settings = get_settings()
    if settings.auth_mode == "mock":
        raise RuntimeError("AUTH_MODE=mock 無 token")
    raise NotImplementedError("AUTH_MODE=bff 尚未實作(接 API 階段)")
