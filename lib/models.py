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
Category = Literal["感測器", "系統", "應用", "網路"]

# selectbox 與種子共用;list 型別以相容 3.9 寫法
CATEGORIES = ["感測器", "系統", "應用", "網路"]
SORTABLE = ["id", "title", "value", "category", "created_at"]
DEFAULT_SORT = "id:asc"


@dataclass
class Actor:
    """目前操作者(mock 由開發切換器提供;日後由認證提供)。

    grade：對應後端 JWT grade claim。
      - admin → "super_admin" | "editor" | "viewer"（見後端 AdminRole）
      - user  → "free" | "premium"（見後端 UserTier）
      - None  → 未知或不需判斷
    """

    username: str
    role: Role          # "user" | "admin"
    grade: Optional[str] = None  # admin_role 或 user_tier


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


@dataclass
class Page:
    items: list  # List[Record]
    total: int  # 篩選後總筆數(未分頁前)
    page: int  # 1-based
    size: int


@dataclass
class RowError:
    row_index: int  # 0-based(對應輸入檔第幾列)
    reason: str


@dataclass
class ImportResult:
    created: int
    errors: list  # List[RowError]


def can_write(actor: Actor) -> bool:
    """寫入權限單一真相（供多頁按鈕 disabled gate 共用）。

    super_admin / editor → True；viewer → False；role='user' → False（latent 防線）。
    """
    if actor.role != "admin":
        return False
    return actor.grade != "viewer"


def can_edit(record: Record, actor: Actor) -> bool:
    """編輯權限判斷（供 mock 來源與頁面按鈕共用，單一真相）。

    - admin + grade="viewer" → 唯讀，不可編輯（任何記錄）
    - admin（其他 grade） → 可編輯任何記錄
    - user → 只可編輯自己建立的記錄
    """
    if actor.role == "admin":
        return actor.grade != "viewer"
    return record.created_by == actor.username


# --- 域例外(data-source §例外;mock 與 api 同契約)---


class RecordNotFound(Exception):
    """get/update/delete 遇不存在或已軟刪除的 id(對應後端 404)。"""


class PermissionDenied(Exception):
    """update/delete 的 actor 非創建者且非 Admin(對應後端 403)。"""


class ValidationError(Exception):
    """建立 / 更新 / 查詢欄位不合法(對應後端 400 / 422)。"""


class NotAuthenticated(Exception):
    """reactive refresh 後仍 401,session 失效(對應 401)。見 auth §5。"""
