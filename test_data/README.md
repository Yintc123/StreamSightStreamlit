# 測試資料

供「資料管理」頁（`pages/data_management.py`）的**匯入**分頁手動上傳測試用。

| 檔案 | 說明 |
|------|------|
| `import_sample.csv` | CSV 匯入測試檔（含表頭，16 列） |
| `import_sample.json` | JSON 匯入測試檔（物件陣列，12 列） |

## 格式規則

- 必填欄位：`title`（非空）、`value`（數值）、`category`（需為 `感測器` / `系統` / `應用` / `網路` 之一）
- 選填欄位：`note`
- 單檔上限 1000 列，編碼 UTF-8
