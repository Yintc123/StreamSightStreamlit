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


class AdminRole:
    """後端 AdminRole IntEnum 對應數值（JWT grade claim 與 API admin_role 均為 int）。"""
    VIEWER      = 0
    EDITOR      = 50
    SUPER_ADMIN = 100
    ROOT        = 999

# selectbox 與種子共用;list 型別以相容 3.9 寫法
CATEGORIES = ["感測器", "系統", "應用", "網路"]
SORTABLE = ["id", "title", "value", "category", "created_at"]
DEFAULT_SORT = "id:asc"
BULK_MAX_ROWS = 1000


@dataclass
class Actor:
    """目前操作者(mock 由開發切換器提供;日後由認證提供)。

    grade：對應後端 JWT grade claim（int）。
      - admin → AdminRole 數值 0/50/100/999（見 AdminRole 常數）
      - user  → None（本系統 admin-only，user 為 latent 分支）
      - None  → 未知/未設定，can_write 視為 VIEWER（安全預設）
    """

    username: str
    role: Role          # "user" | "admin"
    grade: Optional[int] = None  # AdminRole 數值；user → None


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

    grade > AdminRole.VIEWER（>0）→ True；VIEWER（0）或 None → False；role='user' → False（latent 防線）。
    """
    if actor.role != "admin":
        return False
    return (actor.grade or 0) > AdminRole.VIEWER


def can_edit(record: Record, actor: Actor) -> bool:
    """編輯權限判斷（供 mock 來源與頁面按鈕共用，單一真相）。

    - admin + grade="viewer" → 唯讀，不可編輯（任何記錄）
    - admin（其他 grade） → 可編輯任何記錄
    - user → 只可編輯自己建立的記錄
    """
    if actor.role == "admin":
        return can_write(actor)
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
