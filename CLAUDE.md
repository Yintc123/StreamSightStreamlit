# CLAUDE.md

本檔案為 Claude Code 在此 repo 工作時的指引。**所有開發一律嚴格遵守 TDD（測試驅動開發）。**

> **語言**：一律用繁體中文回答（含說明、摘要、commit 訊息與程式碼註解；技術名詞可保留原文）。

## 專案概觀

StreamSight 的 Streamlit 前端應用。以 `st.navigation` + `st.Page` 組成 6 頁多頁面架構，依登入角色動態註冊；即時監控可連後端 FastAPI WebSocket。

- 語言：Python 3.11+ ／ 套件管理：`pip` + `requirements.txt`（虛擬環境 `.venv`）
- 框架：Streamlit
- 測試：`pytest` ＋ `streamlit.testing.v1.AppTest`（頁面互動測試）
- 樣式：主題優先（`.streamlit/config.toml`），CSS 最小化（見設計系統規格）

規格文件集中於 `docs/`：

- [技術架構](docs/architecture.md)（方案 A 純 Streamlit ／ 方案 B ＋ FastAPI）
- [前端頁面結構](docs/specs/frontend-pages.md)（6 頁與存取控制）
- [設計系統 / 樣式規格](docs/specs/design-system.md)（主題 Token 與 CSS 規範）

---

## ⚠️ 開發模式：嚴格 TDD（不可跳過）

**任何功能程式碼的變更，都必須先有一個失敗的測試。** 這是本專案不可協商的規則。

### Red → Green → Refactor 循環

對每一個行為（不是每一個檔案）重複以下步驟：

1. **RED — 先寫測試，並確認它會失敗**
   - 在寫任何實作前，先寫一個能表達「期望行為」的測試。
   - 執行測試，**親眼確認它因為正確的理由失敗**（不是 import error、不是打錯字）。
   - 若測試沒有失敗，代表測試無效或功能已存在——停下來釐清。

2. **GREEN — 寫剛好能讓測試通過的最少程式碼**
   - 只寫足以讓當前失敗測試變綠的實作，不要提前實作未被測試涵蓋的功能。
   - 執行測試，確認由紅轉綠，且未弄壞其他既有測試。

3. **REFACTOR — 在綠燈保護下重構**
   - 測試全綠後才整理程式碼（命名、去重、抽層），每次重構後都重跑測試維持全綠。

### 對 Claude 的硬性要求

- **禁止**在沒有對應失敗測試的情況下新增或修改業務邏輯。若使用者要求直接寫實作，先提出「我會先補一個失敗測試」，除非使用者明確要求跳過。
- 一次只推進一個小步驟：一個測試 → 一段實作 → 跑測試。不要一次寫一大段實作再補測試。
- 每個步驟都要**實際執行** `pytest` 並回報結果，不能只憑推理宣稱通過。
- Bug 修復同樣走 TDD：**先寫一個能重現 bug 的失敗測試**，再修到它變綠（回歸測試）。
- 完成一項工作前，必須跑過完整檢查（見下方「提交前檢查」）並全數通過。

### 可測試性設計

- **邏輯與 UI 分離**：認證、角色判斷、資料處理、統計等純邏輯抽到 `lib/`，以純函式撰寫，方便單元測試。
- Streamlit 頁面（`app.py` / `pages/`）盡量薄，只做排版與呼叫 `lib/`。

### 測試分層與放置位置

- `tests/unit/` — 單元測試，隔離 `lib/` 內單一函式 / 模組的邏輯。
- `tests/app/` — 以 `AppTest` 驅動頁面互動（登入流程、角色動態註冊、表單）。
- 新增 `lib/` 邏輯 → 需有 unit 測試；新增 / 修改頁面行為 → 需有 `AppTest` 測試。
- 測試檔名 `test_*.py`，對應被測模組；共用測試資料與 fixtures 放 `tests/conftest.py`。

---

## 常用指令

```bash
# 建立並啟用虛擬環境
python -m venv .venv
source .venv/bin/activate

# 安裝相依
pip install -r requirements.txt

# 測試（TDD 主要迴圈）
pytest                                  # 全部測試
pytest tests/unit -v                    # 只跑 unit
pytest tests/app -v                     # 只跑頁面（AppTest）
pytest -k <關鍵字>                       # 只跑符合名稱的測試（RED 階段常用）
pytest -x                               # 遇第一個失敗即停

# 啟動應用
streamlit run app.py
```

### 提交前檢查（全數需通過）

```bash
pytest
```

> 若之後導入 lint / 型別檢查（如 `ruff` / `pyright`），一併加入此清單並對齊 CI。

---

## 專案結構

```
app.py                     # 進入點：認證判斷 + st.navigation
pages/
├── dashboard.py           # 2. 儀表板
├── data_management.py     # 3. 資料管理
├── realtime_monitor.py    # 4. 即時監控（連 FastAPI WebSocket）
├── analytics.py           # 5. 資料分析
└── admin.py               # 6. 系統管理（僅 Admin 註冊）
lib/
├── auth.py                # 認證 / 角色 helper（純邏輯，優先測試）
├── state.py               # session_state helper
└── theme.py               # load_css() 樣式載入
styles/main.css            # 共用自訂 CSS
.streamlit/config.toml     # 主題（顏色 / 字型）
tests/                     # unit / app 測試
docs/                      # 架構與頁面 / 樣式規格
```

新功能通常會同時觸及邏輯與頁面：**先在 `lib/` 寫失敗的單元測試 → 補足邏輯 → 再以 `AppTest` 補頁面行為測試。**

---

## 慣例與注意事項

- **邏輯不寫在頁面裡**：可測試的邏輯放 `lib/`，頁面只負責排版與呼叫。
- **存取控制**：角色存於 `st.session_state`；非 Admin **動態不註冊**系統管理頁（比隱藏連結安全），此行為需有測試覆蓋。
- **樣式**：遵循[設計系統規格](docs/specs/design-system.md)——能用 `config.toml` 主題解決就不寫 CSS；CSS 集中於 `styles/main.css`，於進入點載入一次。
- **快取**：查詢類資料善用 `st.cache_data` 並設短 TTL，避免每次 rerun 重查。
- **套件安裝**：一律走 `pip` + `requirements.txt`；**不得透過 Homebrew 安裝**。

---

## 黃金守則

> 沒有先失敗的測試，就不寫功能程式碼。
> Red 一定要親眼看到，Green 只寫最少實作，Refactor 只在全綠時進行。
</content>
