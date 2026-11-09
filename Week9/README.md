# Week 9：將個人作品集網站遷移至 Cloudflare

本週課程介紹 Cloudflare，作業目標是把既有網站改為部署於 Cloudflare 平台。我選擇改寫先前完成的個人作品集網站（[smashcldew/test_website](https://github.com/smashcldew/test_website)），將原本分散在三個服務商的架構整合到 Cloudflare。

## 遷移前後架構對照

| 層級 | 原本 | 遷移後 | 更換原因 |
| --- | --- | --- | --- |
| 前端 | GitHub Pages | Cloudflare Pages | 與後端同平台管理 |
| 後端 | Render（Python / FastAPI） | Cloudflare Workers（JavaScript） | 邊緣運算，無閒置休眠問題 |
| 資料庫 | MongoDB Atlas | Cloudflare D1（SQLite） | Workers 執行環境無法使用 pymongo 驅動 |
| 圖片儲存 | ImgBB API | ImgBB API（沿用） | Cloudflare R2 需綁定付款資訊 |
| 保持喚醒 | cron-job 定時發送 GET | 不需要 | Workers 無休眠機制 |

原架構最大的問題是 Render 免費方案會在閒置後休眠，首次請求需要數十秒冷啟動，因此必須額外用 cron-job 定時發送 GET 請求維持喚醒。改用 Workers 後，這個繞道的做法完全不需要存在。

## 後端改寫

### 執行環境的限制

Workers 不是容器，而是執行在 V8 isolate 上的 JavaScript 環境，無法直接搬移 Python 程式碼。原本的 FastAPI 後端必須整個改寫，主要的對應關係如下：

| FastAPI | Workers |
| --- | --- |
| 路由裝飾器 `@app.get("/api/projects")` | `fetch` 處理函式內比對 `pathname` 與 `method` |
| `Depends(verify_token)` 依賴注入 | 各路由前呼叫 `isAuthorized()` |
| `pymongo.MongoClient` | `env.DB.prepare(...).bind(...)` |
| Pydantic 模型驗證 | 手動檢查欄位型別 |
| `.env` + `python-dotenv` | Wrangler secrets |

### Binding 機制

Cloudflare 以 binding 把外部資源注入 Worker，設定寫在 `wrangler.toml`：

```toml
[[d1_databases]]
binding = "DB"
database_name = "blog_backend"
database_id = "..."
```

程式碼中即可用 `env.DB` 取得資料庫連線。這裡的設計值得注意：**資源名稱與程式碼變數名稱是分離的**。`database_name` 是 Cloudflare 端的識別，`binding` 是程式碼端的變數名。資料庫改名時只需修改設定檔，程式碼不必變動。

### 機密管理

原本使用 `.env` 搭配 `python-dotenv`，檔案以 `.gitignore` 排除。改用 Wrangler secrets 後，值儲存在 Cloudflare 端，本機不存在任何含機密的檔案：

```sh
npx wrangler secret put ADMIN_USER
npx wrangler secret put ADMIN_PASSWORD
npx wrangler secret put SECRET_TOKEN
npx wrangler secret put IMGBB_API_KEY
```

### 刪除邏輯的修正

MongoDB 是文件資料庫，D1 是 SQLite，改寫過程順便修掉了一個既有的缺陷。原本的刪除實作是取出全部文件後以陣列索引定位：

```python
projects = list(collection.find())
target_id = projects[project_id]["_id"]
collection.delete_one({"_id": target_id})
```

這個做法在兩人同時操作時會刪錯資料，因為索引會隨其他人的新增或刪除而位移。改寫為 D1 後直接使用主鍵：

```javascript
await env.DB.prepare("DELETE FROM projects WHERE id = ?").bind(id).run();
```

前端的刪除按鈕也同步從傳遞陣列索引改為傳遞資料庫 id。

## 資料搬移

撰寫 `worker/scripts/mongo_to_d1.py`，從 MongoDB 讀出文件並產生 D1 可執行的 SQL 檔，再以 Wrangler 匯入：

```sh
python mongo_to_d1.py
npx wrangler d1 execute blog_backend --remote --file=scripts/migrate.sql
```

字串中的單引號需 escape 為兩個單引號，否則 SQL 語法會中斷。

## 部署流程

```sh
cd worker
npm install
npx wrangler login
npx wrangler d1 create blog_backend          # 取得 database_id 填入 wrangler.toml
npx wrangler d1 execute blog_backend --remote --file=schema.sql
npx wrangler secret put ADMIN_USER           # 其餘 secret 同此
npx wrangler deploy
```

前端於 Cloudflare Dashboard 以 Pages 連接 GitHub repo，build output directory 設為 `front`，無需建置指令。

## 遇到的問題與解決

### PowerShell 禁止執行腳本

執行 `npm` 時出現無法載入 `npm.ps1`。原因是 PowerShell 的執行原則預設為 `Restricted`，禁止所有腳本檔。Windows 版 npm 有 `npm`、`npm.cmd`、`npm.ps1` 三個進入點，在 PowerShell 中會走 `.ps1` 而被攔下。

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

選用 `RemoteSigned` 而非 `Unrestricted`，保留「網路下載的腳本需有數位簽章」這層防護。

### 各服務的命名規則不一致

四種資源的命名限制並不相同，踩過一次才釐清：

| 資源 | 允許字元 |
| --- | --- |
| D1 資料庫名稱 | 可使用底線 |
| R2 bucket 名稱 | 僅小寫字母、數字、連字號 |
| Worker 名稱 | 僅小寫字母、數字、連字號 |
| Binding | 須為合法的 JavaScript 變數名稱 |

規律是：**會出現在網址中的名稱不能使用底線**，因為 Worker 名稱與 bucket 名稱都會成為網域的一部分。

### 中文內容輸出時的編碼錯誤

執行搬移腳本時出現 `UnicodeEncodeError: 'cp950' codec can't encode character '‹'`。原因是 Windows 的 Python stdout 預設使用 cp950（Big5），而作品內容含有 `‹` 字元，Big5 字集沒有這個字。

更進一步，即使改用 `>` 轉向也仍會失敗，因為 PowerShell 的轉向預設以 UTF-16 加 BOM 寫檔，D1 無法解析。檢查產生出的檔案可以確認這點：

```text
0000000 377 376   I  \0   N  \0   S  \0   E  \0   R  \0   T  \0
```

開頭的 `377 376` 即 UTF-16LE 的 BOM，且每個 ASCII 字元後都跟著一個空位元組。

解法是不經過 stdout，由腳本直接寫檔並明確指定編碼：

```python
with open(out_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(...)
```

### CORS 設定造成的隱性錯誤

Worker 的 CORS 來源原先填入佔位字串，而程式碼邏輯為 `env.ALLOWED_ORIGIN || "*"`。由於該變數有值（只是值是假網域），不會退回 `*`，導致任何真實網頁發出的請求都被瀏覽器攔截。部署前先將該行註解，待 Pages 網址確定後再填入並重新部署。

這類錯誤的特徵是「設定看起來有填，但內容無效」，比留空更難發現。

### R2 需要綁定付款資訊

原計畫以 R2 取代 ImgBB，但建立 bucket 時被要求綁定付款資訊。權衡後決定沿用 ImgBB，僅將 API Key 從 `.env` 改為 Wrangler secret 管理。`wrangler.toml` 中保留註解，說明日後如何改接 R2。

## 成果

| 項目 | 位置 |
| --- | --- |
| 前端網站 | <https://test-website-386.pages.dev> |
| 後端 API | <https://blog-api.cldew20070210.workers.dev> |
| 專案 repo | [smashcldew/test_website](https://github.com/smashcldew/test_website) |

## 心得

這次遷移讓我理解到平台的執行模型會直接決定架構選擇。Workers 的 V8 isolate 模型帶來免冷啟動的優勢，代價是不能使用任意語言與原生套件，因此 MongoDB 驅動無法沿用，必須連資料庫一起更換。一個看似只是「換部署位置」的需求，實際上牽動了整個後端的技術選型。

另外，整個過程中真正耗時的並不是改寫程式邏輯，而是環境與工具鏈的細節：執行原則、字元編碼、命名規則、付費門檻。這些在教學文件上通常不會提及，卻佔據了大部分的除錯時間。
