"""資料分析純函式模組。

輸入均為 pandas DataFrame（DatetimeIndex=created_at, columns=[value, category]）。
所有函式無 Streamlit 依賴，可直接單元測試。
見規格 docs/specs/pages/05-analytics.md。
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from lib.models import Record


def records_to_df(records: List[Record]) -> pd.DataFrame:
    """List[Record] → DataFrame（DatetimeIndex=created_at, columns=[value, category]）。"""
    if not records:
        return pd.DataFrame(columns=["value", "category"])
    df = pd.DataFrame(
        [{"created_at": r.created_at, "value": r.value, "category": r.category}
         for r in records]
    )
    df = df.set_index("created_at")
    df.index = pd.DatetimeIndex(df.index)
    return df


def agg_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """回傳 {sum, mean, max, min}；空 df → 全為 None。"""
    if df.empty:
        return {"sum": None, "mean": None, "max": None, "min": None}
    return {
        "sum": float(df["value"].sum()),
        "mean": round(float(df["value"].mean()), 2),
        "max": float(df["value"].max()),
        "min": float(df["value"].min()),
    }


def agg_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """groupby category → sum/mean/max/min；空 df → 空 DataFrame。"""
    if df.empty:
        return pd.DataFrame()
    return df.groupby("category")["value"].agg(["sum", "mean", "max", "min"])


def resample_series(df: pd.DataFrame, freq: str) -> pd.Series:
    """以指定粒度重採樣 value 欄位（需 DatetimeIndex）。"""
    return df["value"].resample(freq).sum()


def filter_by_date(
    df: pd.DataFrame,
    date_from: Optional[date],
    date_to: Optional[date],
) -> pd.DataFrame:
    """依日期範圍過濾（比對 DatetimeIndex.date）；bound 為 None 時不過濾。"""
    if df.empty:
        return df
    result = df
    if date_from is not None:
        result = result[result.index.date >= date_from]
    if date_to is not None:
        result = result[result.index.date <= date_to]
    return result


def filter_by_category(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """分類過濾；'全部' → 不過濾。"""
    if category == "全部":
        return df
    return df[df["category"] == category]


def build_export_caption(
    category: str,
    date_from: Optional[date],
    date_to: Optional[date],
    count: int,
) -> str:
    """匯出分頁的篩選摘要文字（純函式，無 Streamlit 依賴）。

    格式：目前篩選：分類={category}[，期間 {from} ~ {to}]，共 {n} 筆
    無設定的日期端以「—」表示。
    """
    parts = [f"分類={category}"]
    if date_from is not None or date_to is not None:
        d_from = date_from.strftime("%Y/%m/%d") if date_from else "—"
        d_to = date_to.strftime("%Y/%m/%d") if date_to else "—"
        parts.append(f"期間 {d_from} ~ {d_to}")
    parts.append(f"共 {count} 筆")
    return "目前篩選：" + "，".join(parts)


def make_excel_bytes(df: pd.DataFrame) -> bytes:
    """DataFrame → Excel bytes（openpyxl engine）；空 df 也不拋例外。
    tz-aware datetime 欄位自動轉為 UTC naive（Excel 不支援含時區的 datetime）。
    """
    export = df.copy()
    for col in export.select_dtypes(include=["datetimetz"]).columns:
        export[col] = export[col].dt.tz_convert(None)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export.to_excel(writer, index=False)
    return buf.getvalue()
