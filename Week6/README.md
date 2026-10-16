# Docker 微服務學習與展示

這個專案用 Docker Compose 啟動一個小型微服務系統，並以網頁展示服務健康狀態、留言、統計和質數運算。入口是 Nginx；Node.js、Python、Rust 和 PostgreSQL 都在 Compose 建立的內部網路中互相通訊。

## 服務架構

| 容器 | 技術 | 用途 |
| --- | --- | --- |
| `nginx` | Nginx 1.27（非 root） | 靜態網頁、反向代理；唯一對主機開放 `8080` |
| `node` | Node.js 20、Express、pg | 建立與查詢留言 |
| `python` | Python 3.12、Flask、psycopg | 讀取留言並計算字詞頻率和平均長度 |
| `rust` | Rust | 計算指定上限內的質數 |
| `db` | PostgreSQL 16 | 儲存留言；資料放在 named volume |

瀏覽器開啟 <http://localhost:8080>。Nginx 以非 root 使用者監聽容器的 `8080`，並依路徑把 `/api/node/`、`/api/python/`、`/api/rust/` 轉給對應服務。Node 和 Python 以 Compose 服務名稱 `db` 連資料庫，不使用 `localhost`。健康狀態卡每五秒更新；例如停掉 Python 後，統計和 Python 狀態會顯示離線，留言與 Rust 功能仍可各自運作。

```text
瀏覽器 ── localhost:8080 ──> nginx
                               ├── /api/node/   ──> node ──┐
                               ├── /api/python/ ──> python ├──> db
                               └── /api/rust/   ──> rust   │
                                                          └── postgres_data volume
```

## 啟動與操作

需要安裝 Docker Desktop（含 Docker Compose v2），在專案目錄執行：

```sh
docker compose up --build -d
docker compose ps
```

瀏覽 <http://localhost:8080>。停止服務但保留資料：

```sh
docker compose stop
docker compose start
```

停止並移除容器與網路，named volume 仍會保留：

```sh
docker compose down
```

以下操作用來示範微服務互相獨立：

```sh
docker compose stop python
docker compose ps
docker compose start python
```

若要**連留言資料一起刪除**，才執行：

```sh
docker compose down -v
```

`-v` 會移除 Compose 管理的 `postgres_data`，資料無法從這個 volume 還原。重新建立資料庫後，`db/init.sql` 會再執行。

## 核心概念

- **Image（映像檔）**：建置容器的唯讀模板。`docker compose build` 依各服務的 Dockerfile 建置 image；同一個 image 可以建立多個容器。
- **Container（容器）**：image 執行後的隔離程序。容器可替換、可停止；容器檔案系統中的一般資料不適合當永久儲存。
- **Volume（磁碟區）**：由 Docker 管理、可跨容器生命週期保存的資料空間。`postgres_data` 掛載到 PostgreSQL 資料目錄，所以移除 `db` 容器不會清掉留言。
- **Network（網路）**：Compose 建立 `app_net`，讓服務透過服務名稱彼此尋址，例如 `node` 連線到主機名稱 `db:5432`。只有 Nginx 的 `8080:80` 發佈到主機，資料庫和 API 沒有對外 port。
- **Compose**：以 `docker-compose.yml` 描述服務、建置、環境變數、網路、volume、健康檢查與啟動依賴，集中操作整個系統。
- **反向代理**：瀏覽器只知道 Nginx；Nginx 根據 API 路徑把請求送到內部服務，也提供靜態網頁。

## 常用 Docker 指令

```sh
docker compose up --build -d       # 建置 image，背景啟動服務
docker compose ps                  # 查看容器及健康狀態
docker compose logs -f             # 持續查看全部服務日誌
docker compose logs -f node         # 只看 Node 日誌
docker compose exec db psql -U demo -d docker_demo  # 進入資料庫命令列
docker compose build node          # 只重建 Node image
docker compose restart node        # 重啟 Node 容器
docker compose stop python         # 停止單一服務
docker compose down                # 移除容器與網路，保留 named volume
docker compose down -v             # 同時刪除 named volume 和資料
docker image ls                    # 列出本機 images
docker volume ls                   # 列出 volumes
docker network ls                  # 列出 networks
docker system df                   # 查看 Docker 磁碟使用量
```

## Dockerfile 寫法重點

1. **善用快取分層**：先複製相對少變動的依賴清單，再安裝依賴，最後才複製常改的程式碼。只改程式時，套件安裝層可沿用快取。例如 Node Dockerfile 先 `COPY package*.json`、`npm ci`，再複製 `server.js`；Python 也先複製 `requirements.txt`。
2. **Multi-stage build**：用多個 `FROM` 階段分開建置和執行，執行階段只複製必要成果。Rust 在 builder 編譯，最終 image 只包含執行檔和精簡 Alpine 基底，減少 image 體積與工具數量。
3. **不要以 root 執行程式**：使用 `USER node` 或建立專用的 `appuser`，讓服務程序權限降到最低。若容器遭利用，能操作的範圍也較小。
4. **明確設定工作目錄與啟動命令**：`WORKDIR` 讓路徑一致；以 JSON 格式的 `CMD` 啟動主要程序，容器生命週期就能跟服務程序一致。
5. **避免把機密寫進 image**：正式環境應使用安全的 secret 管理方式。本範例的資料庫帳密只供本機教學，不可直接用於正式環境。

## 實作時容易忽略的地方

- **容器中的 `localhost` 是容器自己。** Node/Python 要連 PostgreSQL，主機名稱應填 Compose 服務名稱 `db`，port 為容器內的 `5432`。
- **`depends_on` 預設只處理啟動順序，不代表資料庫已能接受連線。** 本範例的 db 有 `pg_isready` healthcheck，Node 和 Python 使用 `condition: service_healthy` 等待資料庫就緒。
- **初始化 SQL 只在空資料目錄執行。** PostgreSQL 官方 image 只在 `/var/lib/postgresql/data` 為空時處理 `/docker-entrypoint-initdb.d/` 裡的腳本。已存在的 `postgres_data` 不會因為修改 `init.sql` 而自動重跑。
- **`proxy_pass` 結尾的斜線會改變路徑。** 例如 `location /api/node/` 搭配 `proxy_pass http://node:3000/;`，Nginx 會用 `/` 取代符合的 `/api/node/` 前綴，因此 `/api/node/messages` 送到 Node 時是 `/messages`。若寫成 `proxy_pass http://node:3000;`（沒有結尾 `/`），原 URI 會保留，Node 收到 `/api/node/messages`。
- **健康狀態和程序存在是兩件事。** 這裡 Node/Python 的 `/health` 也檢查 PostgreSQL，所以 DB 不可用時健康檢查會失敗；瀏覽器逐一呼叫服務健康端點，能看出哪個 API 暫時離線。

## 專案檔案

```text
.
├── docker-compose.yml
├── db/init.sql
├── node/Dockerfile, package.json, server.js
├── python/Dockerfile, requirements.txt, app.py
├── rust/Dockerfile, main.rs
└── nginx/Dockerfile, nginx.conf, html/
```
