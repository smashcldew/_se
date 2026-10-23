# Week 7：HW2 測試指南

本資料夾保存 HW2 校務系統的自動化測試與測試報告。測試分成直接呼叫業務邏輯的單元測試、透過 HTTP API 驗證服務行為的系統測試，以及使用 Playwright 操作瀏覽器的端對端（E2E）測試。

## 測試統計

依目前測試程式中的 `test_*` 方法統計，共 **37 項**：

| 類別 | 檔案 | 數量 | 涵蓋範圍 |
| --- | --- | ---: | --- |
| 單元測試 | `tests/test_unit.py` | 10 | 認證、角色、課程、選課、請假、隔離與備份 |
| 單元測試 | `tests/test_attendance.py` | 7 | 點名資料驗證、權限、批次保存、課堂摘要及資料庫升級 |
| **單元測試小計** |  | **17** | 直接測試 Python 業務邏輯及 SQLite 資料 |
| 系統測試 | `tests/test_system.py` | 7 | 登入、權限、HTTP 流程、管理功能、靜態路由及資料保存 |
| 系統測試 | `tests/test_attendance.py` | 4 | 點名 HTTP 路由、角色範圍、篩選與持久化 |
| **系統測試小計** |  | **11** | 經本機 HTTP 伺服器呼叫 API |
| 瀏覽器 E2E | `tests/test_e2e.py` | **9** | 真實瀏覽器中的登入、角色工作流程、點名及介面行為 |
| **總計** |  | **37** | 詳細執行環境與既有驗證紀錄見 [`test-report.md`](test-report.md) |

測試由 `unittest` 執行；每項測試使用臨時 SQLite 資料庫。系統與 E2E 測試啟動本機 HTTP 服務，使用動態連接埠，測試結束後關閉服務並清理資料。上表是依目前程式碼的測試方法數量計算；報告記載這 37 項在原先驗證輪次全部通過，重新執行結果以當次執行為準。

## 單元測試：`tests/test_unit.py`（10 項）

1. **`test_passwords_are_salted_and_verify` — 密碼雜湊**：同一密碼重複雜湊會產生不同結果，雜湊格式為 Argon2id；正確密碼可驗證，錯誤密碼不能通過。
2. **`test_seed_idempotency_and_constraints` — 初始化與資料庫限制**：確認必要資料表及預設使用者、課程存在；重複初始化不增加種子資料，無效外鍵寫入會被 SQLite 拒絕。
3. **`test_sessions_expire_and_logout_revokes` — Session 生命週期**：有效 token 可驗證，偽造 token、已過期 token 和登出後的 token 均遭拒；同時確認資料庫只保存 token 的 SHA-256 雜湊。
4. **`test_role_rules` — 角色授權**：管理員可通過管理員角色檢查；學生嘗試管理員／教師權限時回傳 403。
5. **`test_search_name_and_code` — 課程搜尋**：可依課名「資料庫」與課程代碼 `CS101` 找到相符課程；不匹配的搜尋不回傳結果。
6. **`test_duplicate_capacity_and_missing_course` — 選課錯誤條件**：重複選課與課程額滿回傳 409；選不存在的課程回傳 404。
7. **`test_concurrent_enrollment_never_overbooks` — 併發額滿保護**：兩位學生同時爭取只剩一個名額的課程時，結果恰為一人成功、一人收到 409，不會超收。
8. **`test_student_time_conflict` — 學生課程衝堂**：建立重疊時段後，學生已選一門課再選衝堂課程會收到 409。
9. **`test_leave_dates_and_state_transition` — 請假日期與審核狀態**：拒絕不存在日期、倒置日期與空白原因；學生、行政、管理員不能審核，教師可核准；未知狀態無效，已完成審核不能再次變更，並保存審核人與時間。
10. **`test_isolation_and_backup` — 資料範圍與備份**：行政不能讀取個人課表，學生只能取得自己的課表／請假資料；備份資料庫包含預期使用者資料。

## 點名單元測試：`tests/test_attendance.py`（7 項）

1. **`test_updates_periods_and_history` — 更正、節次與歷史保留**：同課程、學生、日期與節次再次儲存會更新原紀錄；其他節次另存。退選後仍保留歷史，已有點名資料的課程或相關學生不能被刪除。
2. **`test_permissions_and_student_scope` — 寫入權限與查閱範圍**：只有該課授課教師可登錄／取得名單；學生、行政、管理員及其他教師不能代寫。學生看不到別人的紀錄，行政可依授權查閱。
3. **`test_validation_and_approved_leave` — 點名欄位及核准請假**：驗證狀態、日期、節次、學生選課資格及備註長度；不存在課程回傳 404。請假狀態只有在存在已核准請假時才可登錄。
4. **`test_initialize_existing_database_preserves_data` — 舊資料庫初始化**：模擬既有資料庫尚無點名表，重新初始化後新增功能所需資料表，同時保留校名、既有使用者及已寫入點名。
5. **`test_roll_call_atomic_updates_and_roster_validation` — 全班批次點名交易**：名單有不合資格學生時整批回滾，連操作紀錄也不留下；有效批次可保存及更正。空名單、重複／非法學生、名單變動都會遭拒，避免半套寫入。
6. **`test_class_summary_lifecycle_and_scope` — 課堂摘要狀態與可見範圍**：開啟課堂會建立摘要但不自動建立個人缺席紀錄；有權學生可見自己的課堂，無關學生看不到。保存點名可關閉課堂，重開不會覆寫其關閉狀態與手填備註；非教師不能開課。
7. **`test_legacy_class_migration_preserves_manual_notes` — 舊點名資料轉課堂摘要**：由舊版個人點名紀錄補建已關閉的課堂摘要；後續初始化仍保留人工修改的狀態與備註。

## 系統測試：`tests/test_system.py`（7 項）

1. **`test_roles_and_authentication_errors` — HTTP 登入與未授權回應**：四種角色可登入並取得正確身分；錯誤密碼回傳 401，未登入及偽造 token 的 API 請求回傳 403。
2. **`test_core_flow_and_restart_persistence` — 主要流程與服務重啟**：經 HTTP 搜尋與選課、建立請假、驗證行政／教師／管理員查閱及只有教師可審核；關閉並重建伺服器後，課表、審核結果、原 session 仍可使用。
3. **`test_permissions_invalid_data_and_expired_session` — API 角色、輸入與過期 Session**：檢查行政、教師、管理員及學生各自可用的課表、課程、請假、帳號與選課 API；越權操作、錯誤 ID／資料型態及過期 Session 回傳預期錯誤碼。
4. **`test_admin_management_settings_and_backup` — 管理 API**：管理員建立帳號時回傳資料不含密碼雜湊；可更新校名、學期及選課開關、建立備份與查詢操作紀錄；關閉選課後新帳號選課遭拒。
5. **`test_csrf_cookie_and_static_assets` — Cookie 防護與靜態路由**：僅 Cookie 的跨站寫入遭拒，帶指定請求標頭可成功；外部 Origin 登出遭拒。根路徑與舊版 `/HW2/static/...` 別名可提供登入頁，敏感路徑、未知頁面及未知 API 回傳 404。
6. **`test_course_management_and_capacity_over_http` — 課程管理與名額**：行政新增、修改、刪除課程；學生可取得唯一名額，第二位學生收到額滿 409；已有人選課時不能刪除課程，退選後才可刪除。
7. **`test_invalid_dates_review_and_student_data_isolation` — 請假驗證與學生資料隔離**：學生不能用查詢參數讀取他人課表或請假資料；無效日期及審核狀態回傳 400；教師可駁回一次，重複審核回傳 409。也檢查課堂摘要路由的建立權限、各角色查閱數量與日期驗證。

## 點名 HTTP 系統測試：`tests/test_attendance.py`（4 項）

1. **`test_class_routes_and_role_scope` — 課堂摘要 API 與角色範圍**：匿名請求及非教師建立課堂會被拒；教師可開課；學生僅看得到自己所屬課堂，行政與管理員可查閱；無效日期回傳 400。
2. **`test_roll_call_route_roles_and_course_scope` — 批次點名 API 權限**：學生、行政、管理員與非授課教師不能提交點名；錯誤節次回傳 400；授課教師可提交有效名單並透過 API 查到紀錄。
3. **`test_roles_filters_and_persistence` — 點名 API 角色、篩選及重啟保存**：只有教師可寫入與取得課程名單；學生只能看自己的資料，教師／行政／管理員依權限查閱。課程、日期篩選及非法參數皆有驗證；重啟服務後資料仍存在，靜態 JS 可讀取。
4. **`test_teacher_cannot_access_other_course` — 教師跨課程隔離**：把課程改由另一位教師授課後，該教師可登錄；原教師不能新增、查詢紀錄或取得該課學生名單，課程也不出現在其可管理清單。

## 瀏覽器 E2E 測試：`tests/test_e2e.py`（9 項）

1. **`test_student_enrollment_and_leave_review` — 學生選課與請假完整流程**：瀏覽器搜尋並選課、確認課表星期／節次／教室，再送出請假。行政與管理員能查閱但沒有審核入口且直接呼叫 API 也遭拒；教師核准後行政與學生都看到已核准結果。
2. **`test_teacher_timetable_and_rejection` — 教師課表與駁回**：教師可查看授課課表，並在請假審核頁駁回示範申請，畫面更新為已駁回。
3. **`test_attendance_module_all_roles` — 點名模組四角色流程**：教師開課及登錄，未核准請假不得選「請假」狀態；保存個人備註與課堂摘要後可修改及關閉，重開仍保留摘要狀態／備註。學生、行政、管理員只能依範圍查看，不能開課或修改，無關學生看不到該課紀錄。
4. **`test_course_roll_call_roster_reopen_and_cancel` — 名單、重開、取消與手機版**：教師對完整選課名單點名，390 px 寬度下視窗不水平溢出；保存後再次開啟會載入既有狀態。修改後直接關閉不保存未送出的更動。
5. **`test_student_cannot_review_and_forged_session` — 越權與失效 Cookie**：學生看不到使用者管理入口，不能審核請假；不存在課程回傳 404。過期 Session 與偽造 Cookie 都無法取得 API 或維持登入。
6. **`test_admin_creates_user_and_changes_settings` — 管理介面建立帳號與設定**：管理員透過表單建立學生、更新學校名稱並關閉選課；新帳號可登入，但課程選課按鈕呈停用狀態。
7. **`test_accordion_upload_and_mobile` — 首頁互動、檔案預覽與手機版**：驗證功能群組展開／收合；檔案選擇拒絕錯誤副檔名、空檔案及超過 10 MB，合法 TXT 可預覽。明確確認檔案尚未上傳；Esc 可關閉視窗並還原焦點，390 px 版面沒有水平溢出。
8. **`test_login_error_password_and_modal_cancel` — 登入錯誤、密碼顯示與視窗取消**：舊入口路徑導向登入頁；錯誤密碼顯示錯誤提示，密碼可切換顯示／隱藏。請假視窗開啟時日期欄取得焦點，取消後關閉；登出重設密碼隱藏狀態。
9. **`test_static_preview_loads_script_and_explains_login` — 靜態預覽模式**：用僅提供靜態檔案的本機伺服器與直接開啟 HTML 兩種方式，確認腳本載入、提示 API 服務未啟動、密碼顯示切換正常；靜態預覽不會假裝登入成功。

## 執行方式

測試要從 `HW2` 專案根目錄執行，因為測試匯入專案的 `school` 套件。先安裝專案依賴；E2E 另需 `requirements-dev.txt` 與 Playwright 瀏覽器。PowerShell 範例：

```powershell
Set-Location ..\HW2
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s ..\Week7\tests -t ..\Week7 -v
```

只跑其中一類測試：

```powershell
python -m unittest discover -s ..\Week7\tests -t ..\Week7 -p test_unit.py -v
python -m unittest discover -s ..\Week7\tests -t ..\Week7 -p test_system.py -v
python -m unittest discover -s ..\Week7\tests -t ..\Week7 -p test_attendance.py -v
python -m unittest discover -s ..\Week7\tests -t ..\Week7 -p test_e2e.py -v
```

`test_attendance.py` 同時含 7 項單元測試與 4 項 HTTP 系統測試。E2E 需可啟動 Playwright 瀏覽器；詳細驗證環境、歷次修正及限制見 [`test-report.md`](test-report.md)。