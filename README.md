# StreamSight (Streamlit)

StreamSight 的 Streamlit 前端應用。

## 需求

- Python 3.9+
- [uv](https://docs.astral.sh/uv/)（套件管理）
- [Streamlit](https://streamlit.io/)

## 快速開始

```bash
# 安裝相依套件（自動建立 .venv）
uv sync

# 啟動應用
uv run streamlit run app.py
```

啟動後於瀏覽器開啟 http://localhost:8501。

## 架構與安全

> ## 🔒 最核心的設計原則:瀏覽器永遠拿不到 JWT
>
> 這是**整個架構設計的第一因**——底下幾乎每個決策,都是為了守住這一條而推導出來的。
>
> JWT(FastAPI 的 Bearer access token)**全程不進瀏覽器**。它只存在 **Streamlit Python server 的記憶體**(`st.session_state["access_token"]`,per-session、不落檔、不寫 log),使用者端只有一顆**加密的共享 session cookie** 與渲染後的 UI。

### 為什麼整個架構長這樣 —— 全都源於上面那條原則

| 設計決策 | 之所以如此,是因為要「瀏覽器拿不到 JWT」 |
|---|---|
| **Streamlit 是純 API Client、不直接連 DB** | 資料與憑證都關在後端邊界之後,前端表面積最小 |
| **唯一 BFF 是 Next.js 主前端;Streamlit 不是 BFF** | 解 cookie(`SESSION_SECRET`)、Redis、refresh 這些危險能力全集中在 BFF,遠離瀏覽器可及範圍 |
| **採 token 交換(Design B),而非「讓前端讀 sessionId + Redis」** | 只交出一顆**短命、可撤銷**的 access token,爆炸半徑限單一使用者;絕不把 JWT 或 session 真相暴露到瀏覽器 |
| **JWT 只存 server 記憶體,不落檔 / 不 log / 不渲染** | 這就是「瀏覽器拿不到」的具體守法;靠遮蔽紀律 + 測試覆蓋維持 |

### 流程(Design B,見 [ADR 0003](docs/decisions/0003-auth-via-bff-token-exchange.md))

1. 使用者在**主前端**登入 → 種下綁父網域的加密 session cookie。
2. 瀏覽器把該 cookie 一併送到 Streamlit server → Streamlit **原封轉發**給 BFF `GET /api/auth/session` 換取身分與**短命 JWT**(Streamlit 不持有 `SESSION_SECRET`、不碰 Redis)。
3. Streamlit server 以 **Bearer JWT** 直連 FastAPI 業務 API。

> **實作紅線**:JWT 屬伺服器端機密,**不得**以 `st.write` / URL / query params / 自訂元件渲染到前端——這會直接違反最核心的設計原則,必須有測試守住。詳見 [認證流程規格](docs/specs/auth-flow.md)。

## 專案結構

```
StreamSightStreamlit/
├── app.py            # Streamlit 進入點
├── pyproject.toml    # 專案設定與相依套件
├── uv.lock           # 鎖定套件版本
└── README.md
```

## 開發

_待補充。_
