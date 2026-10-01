# HW2 測試報告

已依 `plan.md` 第八節執行單元、系統與真實瀏覽器 E2E 測試，最終 21 項全部通過，無失敗、錯誤或跳過。

## 執行環境與結果

- 作業系統：Windows，PowerShell。
- Python：3.13.7，安裝於專案 `.runtime/python/`。
- 套件：argon2-cffi 25.1.0、Playwright 1.63.0。
- 瀏覽器：Microsoft Edge 154.0.4258.48，無頭模式。
- 資料隔離：每個測試建立臨時 SQLite 資料庫；系統及 E2E 測試使用本機動態連接埠，結束後關閉服務並清除測試資料。

| 類別 | 測試數 | 最終結果 |
| --- | --- | --- |
| 單元測試 | 10 | 全部通過 |
| 系統測試 | 7 | 全部通過 |
| 瀏覽器 E2E 測試 | 4 | 全部通過 |
| 合計 | 21 | 全部通過，16.789 秒 |

## 規畫覆蓋對照

| 規畫項目 | 驗證方式 |
| --- | --- |
| 密碼雜湊與帳密比對 | 單元測試確認 Argon2id、隨機 salt 與正確／錯誤密碼；系統測試確認四種角色登入及錯誤帳密 401 |
| token 建立、無效、過期與撤銷 | 單元測試確認 session 驗證、雜湊儲存、過期與登出撤銷；系統測試確認偽造與過期 token 回傳 403；E2E 確認過期／偽造 Cookie 失效 |
| 角色權限 | 單元角色檢查、系統 API 權限拒絕、E2E 學生不能審核請假或使用管理介面 |
| 課程搜尋 | 單元測試依名稱與代碼搜尋；HTTP 及瀏覽器查詢「程式設計」 |
| 選課、重複、額滿 | 單元與 HTTP 測試驗證重複及額滿 409；單元額外驗證併發選課不超額、學生衝堂 |
| 課表與資料隔離 | HTTP 確認選課後課表與跨學生隔離；E2E 確認程式設計位於星期一第 1–3 節、A101，及教師授課課表 |
| 請假日期、原因與狀態 | 單元測試拒絕無效日期、倒置日期、空白原因與非法狀態；確認已審核不能再次審核 |
| 提出、查詢及審核請假 | HTTP 確認行政、教師、管理員都能看到新申請；E2E 完成學生申請、行政核准、學生重查，並驗證教師駁回 |
| 初始化與假資料 | 單元確認八張必要資料表、假帳號與課程、重複初始化不重複插入及外鍵限制 |
| 服務重啟與資料保存 | HTTP 測試停止並重建伺服器，重新初始化同一 SQLite 檔案，確認帳號可登入、原 session 可用、選課及核准紀錄仍存在 |
| 權限及錯誤流程 | HTTP 與 E2E 驗證學生審核遭拒、不存在課程、過期／偽造 session；單元與 HTTP 驗證錯誤資料 |
| 額外既有功能 | HTTP 驗證課程新增／編輯／刪除、退選、帳號新增、選課開關、備份、操作紀錄、Cookie 操作驗證、跨來源拒絕與靜態檔案；E2E 驗證管理員新增帳號並關閉選課 |

## 第一輪發現及修正

第一輪 21 項中，19 項通過、2 項錯誤，均位於測試程式。應用程式碼未變更。

1. `test_isolation_and_backup` 使用 `with sqlite3.connect(...)`，只結束交易而未關閉連線。Windows 清理臨時備份時因檔案仍開啟而發生 `WinError 32`，並出現 `ResourceWarning`。改用 `contextlib.closing` 明確關閉連線。
2. `test_admin_creates_user_and_changes_settings` 在新增帳號後再次登入，頁面仍保留隱藏編輯視窗的帳號欄位。全頁 `get_by_label("帳號")` 匹配兩個元素，觸發 Playwright strict mode 錯誤。登入定位器改限定於 `#login-form`。

同時補上必要資料表驗證、三種審核角色查詢新申請、瀏覽器課程搜尋、課表星期／節次／教室、過期 session 的驗證。修正後一次執行完整三類測試，全數通過。

## 重現方式

在 `HW2` 目錄執行，使用本次已準備好的本機環境與 Edge：

```powershell
$env:HW2_BROWSER_CHANNEL = 'msedge'
$env:PYTHONIOENCODING = 'utf-8'
.\.runtime\python\python.exe -W error::ResourceWarning -m unittest tests.test_unit tests.test_system tests.test_e2e -v
```

最終輸出：

```text
Ran 21 tests in 16.789s

OK
```

若使用 README 的 `.venv` 環境，可替換 Python 路徑；若使用 Playwright Chromium，先安裝 Chromium 並移除 `HW2_BROWSER_CHANNEL` 環境變數。

## 驗證限制

- 重啟測試是在同一 Python 程序中關閉並重建 HTTP 伺服器，未測試作業系統或獨立程序重啟。
- 本次驗證本機 HTTP 與 Edge，未驗證 HTTPS 憑證、其他瀏覽器、外部部署、效能或完整安全性稽核。
- 未修改正式資料庫；成績、學費、公告、教室與點名等預留業務功能不在本次已實作測試範圍。
