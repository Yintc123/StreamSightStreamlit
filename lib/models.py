"""資料契約與純邏輯:Actor / Record 等型別與 can_edit 權限函式。

見規格 docs/specs/data-source.md(§資料契約、§權限純函式)。
相容 Python 3.9:型別註記用 Optional[...],並 from __future__ import annotations。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

try:  # Python 3.8+：Literal 在 typing
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal  # type: ignore

Role = Literal["user", "admin"]


@dataclass
class Actor:
    """目前操作者(mock 由開發切換器提供;日後由認證提供)。"""

    username: str
    role: Role  # "user" | "admin"


@dataclass
class Record:
    id: int
    title: str
    value: float
    category: str
    created_by: str  # username
    created_at: datetime  # UTC
    updated_at: datetime  # UTC
    note: str = ""
    deleted_at: Optional[datetime] = None  # 軟刪除;None = 未刪除


def can_edit(record: Record, actor: Actor) -> bool:
    """Admin 恆可編輯;否則僅創建者本人。供 mock 來源與頁面按鈕共用(單一真相)。"""
    return actor.role == "admin" or record.created_by == actor.username
