# HW1：MiniCurl — Go HTTP 命令列工具

MiniCurl（執行檔名稱為 `mycurl.exe`）是以 Go 撰寫的簡易 HTTP 用戶端，支援自訂請求方法、標頭、請求內容、Cookie、Basic Auth、重新導向與檔案下載，也能同時向多個 URL 發送請求。

## 專案檔案

| 檔案 | 說明 |
| --- | --- |
| `main.go` | 命令列參數解析、HTTP 請求、併發處理與下載進度的程式碼。 |
| `go.mod` | 模組名稱為 `mycurl`，宣告 Go `1.27.1`，使用 `github.com/spf13/pflag v1.0.10`。 |
| `go.sum` | 相依套件的校驗資訊。 |
| `mycurl.exe` | 可直接在 Windows 執行的程式。 |

## 開始使用

以下範例使用 Windows PowerShell，請先進入專案目錄：

```powershell
cd .\HW1
.\mycurl.exe --help
```

基本語法：

```text
.\mycurl.exe [選項] <URL1> <URL2> ...
```

若要從原始碼建置，需準備符合 `go.mod` 宣告的 Go 工具鏈：

```powershell
go mod download
go build -o mycurl.exe .
```

## 使用方式與範例

下表的 HTTP 範例需有網路連線；`payload.json` 需事先建立在目前目錄。

| 功能 | 使用方式 | 範例 |
| --- | --- | --- |
| 查看說明 | `--help` | `.\mycurl.exe --help` |
| GET 請求 | 直接指定 URL，預設方法為 GET | `.\mycurl.exe https://httpbin.org/get` |
| 指定 HTTP 方法 | `-X` 或 `--request` | `.\mycurl.exe -X DELETE https://httpbin.org/delete` |
| 自訂標頭 | `-H` 或 `--header`，可重複指定；同名標頭會被後面的值覆蓋 | `.\mycurl.exe -H 'Accept: application/json' -H 'X-Test: demo' https://httpbin.org/headers` |
| 傳送文字資料 | `-d` 或 `--data`；POST 需明確加上 `-X POST` | `.\mycurl.exe -X POST -H 'Content-Type: text/plain' -d 'Hello MiniCurl' https://httpbin.org/post` |
| 傳送檔案內容 | `-d '@檔名'` 將檔案內容作為請求 body | `.\mycurl.exe -X POST -H 'Content-Type: application/json' -d '@payload.json' https://httpbin.org/post` |
| 儲存回應 | `-o` 或 `--output`，將回應 body 寫入檔案 | `.\mycurl.exe -o response.json https://httpbin.org/get` |
| 查看詳細資訊 | `-v` 或 `--verbose`，顯示請求與回應的標頭 | `.\mycurl.exe -v https://httpbin.org/get` |
| 跟隨重新導向 | `-L` 或 `--location`；預設不跟隨 | `.\mycurl.exe -L https://httpbin.org/redirect/1` |
| 設定逾時 | `-m` 或 `--max-time`，單位為秒，預設 30 秒 | `.\mycurl.exe -m 5 https://httpbin.org/delay/2` |
| Basic Auth | `--user '帳號:密碼'` | `.\mycurl.exe --user 'demo:secret' https://httpbin.org/basic-auth/demo/secret` |
| 自訂 Cookie | `-b` 或 `--cookie`，每次指定一組 `NAME=VALUE`，可重複使用 | `.\mycurl.exe -b 'session=abc123' -b 'theme=dark' https://httpbin.org/cookies` |
| 停用下載進度 | `--no-progress` 搭配檔案輸出 | `.\mycurl.exe --no-progress -o response.json https://httpbin.org/get` |
| 忽略 TLS 憑證驗證 | `-k` 或 `--insecure` | `.\mycurl.exe -k https://localhost:8443`（需有本機 HTTPS 服務） |
| 同時請求多個 URL | 以空白分隔多個 URL，所有 URL 共用指定選項 | `.\mycurl.exe https://httpbin.org/get https://httpbin.org/uuid` |
| 多個 URL 分別存檔 | 多個 URL 搭配 `-o`，依 URL 順序加入編號 | `.\mycurl.exe -o result.json https://httpbin.org/get https://httpbin.org/uuid`，產生 `result_1.json` 與 `result_2.json` |

## 行為說明

- `-d` 不會自動切換為 POST，也不會自動設定 `Content-Type`；請依需求搭配 `-X` 與 `-H`。
- 未指定 `-o` 時，回應 body 輸出到標準輸出；詳細資訊、錯誤與進度輸出到標準錯誤。
- 下載進度只在指定 `-o` 且伺服器提供大於零的內容長度時顯示。
- 多個 URL 會併發執行，直接輸出到終端機時，回應順序不固定且內容可能交錯；可使用 `-o` 分別儲存。
- 輸出檔案若已存在會被覆寫。
