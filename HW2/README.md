# 校務系統（HW2）

以 Python、SQLite 與原生 HTML / CSS / JavaScript 建立的校務系統，支援管理員、行政、學生與老師。開發規畫與進度請見 [plan.md](plan.md)。

**目前 37 項測試皆已通過。** 本輪完整執行 36 項，再新增課堂 API 測試並重驗 2 項相關瀏覽器流程，全部通過。執行環境、修正與驗證限制請見 [test-report.md](../Week7/test-report.md)。啟動環境需 Python 3.11 以上。

## 網頁畫面

登入頁提供帳密輸入、密碼顯示切換與示範帳號。登入後先進入「校務總覽」，顯示課表課程數、待審核請假與選課狀態；主畫面依教務與學習、校園服務、系統管理（管理員限定）與功能擴充分組，可個別折疊或全部展開／收合。側欄也支援分組折疊。

新增／編輯課程與使用者、請假申請、校務設定、備份與刪除確認均採彈出視窗，可按關閉或 Esc 返回，開啟時焦點移至表單。版面支援桌面與手機。

「上傳檔案」位於總覽的「校園服務」，目前為介面預覽：可選擇 PDF、PNG、JPG、TXT，檢查副檔名、非空內容與 10 MB 大小上限，並顯示檔名與大小。尚未連接後端儲存服務，確認預覽不會傳送或保存檔案。

## 啟動方式

已有本機 Python 環境時，可直接執行 HW2 資料夾內的 `start.cmd`，保持視窗開啟，再瀏覽 `http://127.0.0.1:5500/`。啟動檔依序使用 `.venv`、本機 `.runtime` 或系統 Python；若尚未安裝環境，請依下列步驟設定。

Python 校務服務預設使用 5500 埠，請先停止 VS Code Live Server，再執行 `start.cmd`，避免連接埠衝突。頁面與登入 API 都由 Python 提供。Live Server 只提供靜態預覽，沒有登入 API；預覽頁仍可使用密碼「顯示／隱藏」切換，並會提供校務服務入口提示。

原本的 `http://127.0.0.1:5500/HW2/static/index.html` 網址也可使用，Python 服務會自動導向 `/` 登入頁。更新 Python 程式後，請在服務視窗按 Ctrl+C，再重新執行 `start.cmd` 載入修改。

在專案根目錄開啟 PowerShell：

```powershell
cd .\HW2
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

開啟 `http://127.0.0.1:5500` 即可操作網頁介面。第一次啟動會建立 `HW2/data/school.db` 與假資料；之後重啟不會重設帳號或選課紀錄。資料庫路徑預設依 `app.py` 所在位置決定，不受工作目錄影響。

若電腦的 Python 是以 `py` 啟動，可將第一個 `python -m venv .venv` 改為 `py -3 -m venv .venv`。

| 帳號 | 密碼 | 角色 | 用途 |
| --- | --- | --- | --- |
| `admin` | `admin123` | 管理員 | 使用者、系統設定、備份與操作紀錄 |
| `office` | `office123` | 行政 | 課程維護與請假紀錄查閱 |
| `student1` | `student123` | 學生 | 從空課表開始選課、請假 |
| `student2` | `student123` | 學生 | 預載資料庫課程與一筆待審核請假 |
| `teacher1` | `teacher123` | 老師 | 查看授課課表與審核請假 |

假資料包含程式設計、資料庫系統與學術英文。上述帳密供本機示範使用，實際使用前請透過管理員介面更改。

## 功能與權限

| 功能 | 學生 | 老師 | 行政 | 管理員 |
| --- | --- | --- | --- | --- |
| 課程搜尋 | ✓ | ✓ | ✓ | ✓ |
| 選課與退選 | 個人 | — | — | — |
| 課表 | 個人 | 授課 | — | 全校 |
| 提出請假 | 個人 | — | — | — |
| 查詢請假 | 個人 | 全部 | 全部 | 全部 |
| 核准或駁回請假 | — | ✓ | — | — |
| 查閱出缺席 | 個人 | 授課課程 | 全校 | 全校 |
| 登錄／更正出缺席 | — | 授課課程 | — | — |
| 新增、編輯、刪除課程 | — | — | ✓ | ✓ |
| 新增、編輯、停用帳號 | — | — | — | ✓ |
| 選課開關、學校名稱與學期設定 | — | — | — | ✓ |
| 備份與查看操作紀錄 | — | — | — | ✓ |

選課會檢查重複、容量與衝堂，使用 SQLite 寫入交易避免多人同時選課時超額。已有學生選課的課程不可刪除或直接調整上課時間；容量不可低於已選人數。課程維護也會檢查教師與教室的時間衝突。

行政使用課程清單查詢與維護開課資料，不提供全校課表；總覽第一項統計為請假紀錄筆數，且不請求課表 API。行政直接存取 `GET /api/schedule` 會回傳 403。

請假日期必須為有效的 `YYYY-MM-DD`，結束日期不得早於開始日期，原因不可留空。申請只有 `pending`、`approved`、`rejected` 三種狀態，已審核申請不能再次審核。

請假流程為「學生申請 → 老師核准或駁回 → 行政查閱紀錄」。系統自動保存申請、審核狀態、審核老師與時間。行政及管理員僅能查閱請假紀錄，不能核准或駁回；後端 API 同樣限制只有老師能審核。

## API

點名模組已實作，操作方式、模組結構與 API 見 [attendance-module.md](attendance-module.md)。老師在自己的課程旁按「開啟點名」，選定日期與節次後，即可在彈出視窗對全班點名並一次儲存。四種角色均可從「教務與學習 → 出缺席」查閱權限範圍內的紀錄。

出缺席主列表每堂課一列：日期節次、課程、學生人數、狀態（點名中／關閉）、備註／缺席人數（老師自行填寫）、修改。老師按「修改」開啟該堂課視窗；其他角色只能查看明細，學生只見自己的結果。

登入後，網頁使用 HttpOnly / SameSite Cookie；API 呼叫者可使用登入回傳的 Bearer token。Session 有效期為 8 小時，登出後立即撤銷；資料庫只保存 token 雜湊，重啟服務後未到期的 session 仍有效。以 Cookie 進行資料變更時須加上 `X-Requested-With: SchoolPortal`，後端也會拒絕跨來源操作。

| 方法與路徑 | 用途 | 請求內容或說明 |
| --- | --- | --- |
| `POST /api/login` | 登入 | `{"username":"student1","password":"student123"}` |
| `POST /api/logout` | 登出 | `{}` |
| `GET /api/me` | 目前使用者 | 不回傳密碼雜湊 |
| `GET /api/courses?q=資料庫` | 查詢課程 | `q` 可省略 |
| `POST /api/courses` | 新增課程 | 詳見下方範例 |
| `PUT /api/courses/{id}` | 編輯課程 | 與新增相同欄位 |
| `DELETE /api/courses/{id}` | 刪除課程 | 已被選修時拒絕刪除 |
| `GET /api/teachers` | 教師選單 | 啟用中的教師 |
| `POST /api/enroll` | 選課 | `{"course_id":1}` |
| `DELETE /api/enroll/{course_id}` | 退選 | 個人選課 |
| `GET /api/schedule` | 課表 | 學生個人、老師授課、管理員全校；行政無權限 |
| `POST /api/leave` | 申請請假 | `{"start_date":"2026-10-05","end_date":"2026-10-05","reason":"身體不適"}` |
| `GET /api/leave` | 查詢請假 | 範圍依角色決定 |
| `POST /api/leave/{id}/review` | 審核請假（僅老師） | `{"status":"approved"}` 或 `{"status":"rejected"}` |
| `GET /api/users` | 帳號清單 | 管理員 |
| `POST /api/users` | 新增帳號 | `{"username":"student3","password":"student123","full_name":"李同學","role":"student","active":true}` |
| `PUT /api/users/{id}` | 編輯帳號 | 同上；省略 `password` 保留原密碼 |
| `GET /api/settings` | 校務設定 | 已登入；選課開關值為字串 `true` 或 `false` |
| `PUT /api/settings` | 更新設定 | `{"school_name":"校務系統","semester":"115 學年度第一學期","enrollment_open":true}` |
| `POST /api/backup` | 備份資料庫 | 管理員，回傳備份檔名 |
| `GET /api/audit` | 最近 100 筆操作紀錄 | 管理員 |
| `GET /api/modules` | 擴充方向 | 預留功能清單 |

新增課程範例（以 `GET /api/teachers` 回傳的有效教師 ID 取代 `teacher_id`）：

```json
{"code":"CS202","name":"資料結構","teacher_id":5,"credits":3,"capacity":30,"weekday":2,"start_period":1,"end_period":3,"room":"A102"}
```

PowerShell 範例：

```powershell
$base = 'http://127.0.0.1:5500'
$login = Invoke-RestMethod "$base/api/login" -Method Post -ContentType 'application/json' -Body '{"username":"student1","password":"student123"}'
$headers = @{ Authorization = "Bearer $($login.token)" }
Invoke-RestMethod "$base/api/courses" -Headers $headers
Invoke-RestMethod "$base/api/enroll" -Headers $headers -Method Post -ContentType 'application/json' -Body '{"course_id":1}'
Invoke-RestMethod "$base/api/schedule" -Headers $headers
```

錯誤會回傳 `{"error":"說明"}`。錯誤帳密使用 `401`；未登入、登入失效或權限不足使用 `403`；資料格式錯誤使用 `400`；找不到資料使用 `404`；重複選課、額滿、衝堂等衝突使用 `409`。

## 備份、HTTPS 與日誌

```powershell
# 建立備份後結束，或登入管理員後由網頁建立備份
.\.venv\Scripts\python.exe app.py --backup

# 使用自行準備的憑證與私鑰啟動 HTTPS
.\.venv\Scripts\python.exe app.py --cert server.pem --key server-key.pem --port 8443

# 指定不同資料庫或連接埠
.\.venv\Scripts\python.exe app.py --db data/demo.db --port 8001
```

備份位於資料庫所在目錄的 `backups/`，使用 SQLite backup API 建立完整副本。復原時先停止服務，再用 `--db 備份路徑` 指定備份檔啟動。錯誤及 HTTP 操作日誌位於 `logs/school.log`，會輪替保存。HTTPS 模式會為登入 Cookie 加上 Secure 屬性；預設 HTTP 僅用於本機開發。

## 專案結構與擴充

```text
HW2/
├── app.py                  # CLI、日誌與 HTTPS 啟動
├── requirements.txt        # Argon2 密碼套件
├── requirements-dev.txt    # 額外的瀏覽器測試套件
├── school/
│   ├── common.py           # 驗證、錯誤與操作紀錄
│   ├── database.py         # Schema、初始化、假資料與備份
│   ├── auth.py             # 登入、session 與帳號管理
│   ├── courses.py          # 課程搜尋與維護
│   ├── enrollment.py       # 選退課與課表
│   ├── leave.py            # 請假與審核
│   ├── admin.py            # 系統設定與操作紀錄
│   ├── server.py           # HTTP 路由、權限與靜態檔案
│   └── extensions.py       # 新功能註冊入口
├── static/                 # HTML、CSS 與 JavaScript
├── tests/                  # 三類測試來源
├── data/                   # 首次啟動時建立，不提交 Git
├── logs/                   # 執行時建立，不提交 Git
└── plan.md                 # 規畫與開發狀態
```

密碼使用 [argon2-cffi 的 PasswordHasher](https://argon2-cffi.readthedocs.io/en/stable/api.html)，資料表含外鍵、唯一性與狀態限制。資料庫沒有連線到外部服務；首次啟動需要安裝 `requirements.txt` 的套件。

成績、學費、公告通知與教室管理目前列為後續擴充。點名已獨立實作於 `school/attendance.py` 與 `static/attendance.js`，並由 `school/extensions.py` 註冊路由。其他新增模組也可在此註冊，例如：

```python
def register(router):
    router.add("GET", "/api/grades", list_grades, roles=("student", "teacher"))

def list_grades(context):
    # context.db、context.user、context.data、context.query 可供模組使用
    return []
```

## 測試來源（已執行通過）

| 類別 | 檔案 | 範圍 |
| --- | --- | --- |
| 單元測試 | `../Week7/tests/test_unit.py` | 雜湊、session 到期與撤銷、角色、搜尋、重複與額滿、併發選課、衝堂、請假驗證、備份 |
| 系統測試 | `../Week7/tests/test_system.py` | 真實 HTTP API、角色登入、資料隔離、重啟、管理、Cookie 操作驗證與靜態檔案 |
| 點名單元與系統測試 | `../Week7/tests/test_attendance.py` | 課程／角色權限、篩選、重複更新、請假驗證、歷史保存、既有資料庫升級 |
| E2E 測試 | `../Week7/tests/test_e2e.py` | 真實瀏覽器操作選課、課表、學生請假、教師核准與駁回、行政查閱紀錄、管理員新增帳號與設定、權限拒絕 |

測試使用臨時資料庫與臨時伺服器，不使用 `data/school.db`。後續需要驗證時可執行：

```powershell
# 單元與系統測試
.\.venv\Scripts\python.exe -m unittest tests.test_unit tests.test_system tests.test_attendance -v

# 瀏覽器 E2E 測試：僅在需要時安裝
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m unittest tests.test_e2e -v
```

瀏覽器安裝方式參考 [Playwright 官方文件](https://playwright.dev/python/docs/library)。本次使用專案內 `.runtime/python/python.exe` 與已安裝的 Edge 驗證；重現命令請見 [test-report.md](../Week7/test-report.md)。
