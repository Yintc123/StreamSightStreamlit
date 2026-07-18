"""即時監控純函式模組。

以最小依賴示範「即時資料監控」的資料層：決定性模擬生成器、告警判斷、
環形緩衝裁切、DataFrame 轉換與指標卡計算。所有函式**無 Streamlit 依賴**，
可直接單元測試；值生成刻意避開 datetime.now() / 全域 random，改以 (tick, seed)
決定性雜湊，確保同 (tick, seed) → 同值、可重現。

未來接後端（FastAPI WebSocket）時，本模組純函式與頁面版面不變，只替換「取值來源」。
見規格 docs/specs/pages/04-realtime-monitor.md（§純函式契約為單一真相）。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import List

import altair as alt
import pandas as pd

from lib.ui import Metric

# ---------------------------------------------------------------------------
# 常數（單一來源；頁面 import 使用，不散寫魔術數字）
# ---------------------------------------------------------------------------

CHANNEL = "數值"          # DataFrame 欄名 / 圖表圖例
DEFAULT_THRESHOLD = 80.0
VALUE_MIN, VALUE_MAX = 0.0, 100.0
MAX_POINTS = 60           # 環形緩衝上限＝折線圖視窗（trim 用；指標卡「近 N 筆」的 N）
RECENT_POINTS = 15        # 柱狀圖「近況」視窗（buffer[-RECENT_POINTS:]）

# 圖表軸標籤（中文，含單位；折線 / 柱狀圖共用，頁面 import 使用）
X_AXIS_LABEL = "時間（時:分:秒）"   # x 軸＝逐筆時間戳 ts
Y_AXIS_LABEL = "數值（0–100）"      # y 軸＝讀數 value（值域 0–100）
TIME_FORMAT = "%H:%M:%S"           # x 軸刻度時間格式（d3-time-format；明確顯示時:分:秒）


# ---------------------------------------------------------------------------
# 型別定義（純資料，可直接單元測試）
# ---------------------------------------------------------------------------

@dataclass
class Reading:
    """單筆即時讀數。

    ts：產生當下時間（頁面以 datetime.now().astimezone() 標本地時區 aware）。
    value：0–100，一位小數。
    """
    ts: datetime
    value: float


@dataclass
class Alert:
    """告警資料（value 超過 threshold 時）。"""
    value: float
    threshold: float


# ---------------------------------------------------------------------------
# 純函式（供單元測試）
# ---------------------------------------------------------------------------

def sample_value(tick: int, seed: int = 0) -> float:
    """決定性模擬取值：同 (tick, seed) → 同一值；落在 [0, 100]，四捨五入 1 位。

    以 SHA-256 雜湊 (seed, tick) 取前 32 bit 映射至值域，避免 datetime.now() /
    全域 random，確保可重現、利於單元測試。
    """
    digest = hashlib.sha256(f"{seed}:{tick}".encode("utf-8")).hexdigest()
    fraction = int(digest[:8], 16) / 0xFFFFFFFF
    value = VALUE_MIN + fraction * (VALUE_MAX - VALUE_MIN)
    return round(value, 1)


def generate_stream(n: int, start_tick: int = 0, seed: int = 0) -> List[float]:
    """連續 n 個 sample_value；len == n；決定性。"""
    return [sample_value(start_tick + i, seed) for i in range(n)]


def is_over(value: float, threshold: float) -> bool:
    """告警判斷：value 嚴格大於 threshold。"""
    return value > threshold


def alert_message(value: float, threshold: float) -> str:
    """告警文案（純函式，無 Streamlit 依賴）。

    不含前導警示符號——警示圖示交由 st.toast(icon=...) 呈現，避免重複。
    """
    return f"告警：目前值 {value} 已超過閾值 {threshold}"


def readings_to_df(readings: List[Reading]) -> pd.DataFrame:
    """List[Reading] → DataFrame（index=ts DatetimeIndex 由舊到新、單欄 CHANNEL）。

    空 list → 空 DataFrame（欄含 CHANNEL）。
    """
    if not readings:
        return pd.DataFrame(columns=[CHANNEL])
    df = pd.DataFrame(
        [{"ts": r.ts, CHANNEL: r.value} for r in readings]
    )
    df = df.set_index("ts")
    df.index = pd.DatetimeIndex(df.index)
    return df.sort_index()


def build_chart(readings: List[Reading], mark: str = "line") -> "alt.Chart":
    """List[Reading] → Altair 圖表，x 軸為 temporal 且刻度以 TIME_FORMAT 顯示時:分:秒。

    改用 Altair（而非 st.line_chart）的唯一理由：st.line_chart 無法指定刻度時間格式，
    窄時間區間下 Vega-Lite 自動選的刻度難以辨識為時:分:秒。此處明確 format=TIME_FORMAT，
    並以中文含單位標籤標題。mark="line"（趨勢）/ "bar"（近況）。

    內部欄名用 ASCII（ts / value）避免 Altair shorthand 解析中文欄名；中文改由軸 title 呈現。
    空 readings 也回傳合法圖表（不拋例外；頁面正常走 empty_state 分支不會呼叫）。
    """
    data = pd.DataFrame(
        [{"ts": r.ts, "value": r.value} for r in readings],
        columns=["ts", "value"],
    )
    base = alt.Chart(data)
    marked = base.mark_bar() if mark == "bar" else base.mark_line()
    return marked.encode(
        x=alt.X("ts:T", axis=alt.Axis(format=TIME_FORMAT, title=X_AXIS_LABEL)),
        y=alt.Y("value:Q", axis=alt.Axis(title=Y_AXIS_LABEL)),
    )


def summary_metrics(readings: List[Reading], threshold: float) -> List[Metric]:
    """依緩衝計算 4 個 Metric（目前 / 近 N 筆最大 / 近 N 筆平均 / 超標筆數，N = MAX_POINTS）。

    空 list → []（不拋例外，改由頁面 empty_state 呈現）。
    目前值 > 閾值時「目前值」卡帶 delta=round(value-threshold, 1) ＋ delta_color="inverse"
    （st.metric 於 delta=None 時會忽略 delta_color，故超標才給 delta）；否則 delta=None、
    delta_color="off"。其餘卡片不硬塗色，避免設了不會顯示的 no-op。
    """
    if not readings:
        return []
    values = [r.value for r in readings]
    current = values[-1]
    over_count = sum(1 for v in values if is_over(v, threshold))

    if is_over(current, threshold):
        current_metric = Metric(
            label="目前值",
            value=current,
            delta=round(current - threshold, 1),
            delta_color="inverse",
        )
    else:
        current_metric = Metric(
            label="目前值",
            value=current,
            delta=None,
            delta_color="off",
        )

    return [
        current_metric,
        Metric(label=f"近 {MAX_POINTS} 筆最大", value=max(values)),
        Metric(label=f"近 {MAX_POINTS} 筆平均", value=round(sum(values) / len(values), 1)),
        Metric(label="超標筆數", value=over_count),
    ]


def trim(buffer: List[Reading], max_len: int) -> List[Reading]:
    """回傳最後 max_len 筆（max_len >= 0）；不足則原樣回傳；不變更輸入。"""
    if max_len <= 0:
        return []
    return buffer[-max_len:]
