from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_dotenv_in_unit_tests(monkeypatch, tmp_path):
    """unit 測試一律 chdir 到無 .env 的臨時目錄。

    pydantic-settings 讀取 env_file=".env" 是相對 CWD 的路徑；
    若 repo 根目錄有 .env，其內容會覆蓋各環境子類的欄位預設值（如 USE_MOCK）。
    chdir 到空的 tmp_path 確保 unit 測試只看 class default + 明確 setenv。
    需要測試 .env 讀取行為的測試，在測試本體內以 monkeypatch.chdir(tmp_path)
    自行建立 .env，會覆蓋本 autouse fixture 的 chdir。
    """
    monkeypatch.chdir(tmp_path)
