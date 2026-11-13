# echeck-cli（指令：`echeck`）

[English](README.md) | 繁體中文

檢查你的專案有沒有把 `.env`、私鑰、憑證等敏感檔案**保護好**的零相依 CLI / 函式庫。
A zero-dependency CLI and library that checks your secrets (`.env`, keys, credentials) are covered by `.gitignore` / `.dockerignore` / `.npmignore`, are not tracked by git, and are not hard-coded in source.

## 它檢查什麼

| 代碼 | 等級 | 說明 |
| --- | --- | --- |
| `tracked` | 錯誤 | 敏感檔案已經被 git 追蹤（已進入版本紀錄） |
| `not-gitignored` | 錯誤 | 敏感檔案沒有被 `.gitignore` 涵蓋 |
| `secret-in-source` | 錯誤 | 原始碼中疑似寫死 AWS / GitHub / Slack / Discord / Stripe 金鑰、私鑰區塊或密碼 |
| `not-dockerignored` | 警告 | 專案有 Dockerfile，但 `.dockerignore` 沒擋住敏感檔案 |
| `not-npmignored` | 警告 | 專案會 `npm publish`，但敏感檔案沒有被排除 |

會被視為敏感檔案的有：`.env`、`.env.*`（`.env.example` 除外）、`*.pem`、`*.key`、`*.p12`、`id_rsa` 系列、`credentials.json`、`.npmrc`、`.pypirc`、`*.tfstate` 等。

## 安裝與使用

```bash
# 不用安裝，直接執行
npx echeck-cli

# 或全域安裝
npm install -g echeck-cli
echeck ./my-project
```

### 選項

```
--fix         自動把缺少的規則補進 .gitignore
--no-scan     不掃描原始碼中寫死的金鑰（只檢查 ignore 規則）
--scan-tests  連測試資料夾 / 測試檔也掃描內容（預設略過）
--json        以 JSON 輸出結果（方便接 CI）
--strict      連警告也視為失敗
-v, --version 顯示版本
-h, --help    顯示說明
```

結束代碼：`0` 沒問題、`1` 有問題、`2` 執行錯誤。

### 處理誤報

內容掃描只看格式，測試用的假帳號密碼也可能被當成金鑰。有三種處理方式：

1. **測試資料夾預設略過**：`test/`、`tests/`、`__tests__/`、`spec/`、`fixtures/`、`*.test.js`、`test_*.py` 等的**內容**不會被掃描（這些資料夾裡的 `.env` 之類敏感檔仍會檢查）。要納入請加 `--scan-tests`。
2. **行內忽略**：在那一行加上註解 `echeck-ignore`，只略過該行。
   ```python
   PASSWORD = "test1234"  # echeck-ignore
   ```
3. **`.echeckignore`**：在專案根目錄建立，寫法與 `.gitignore` 相同，列出的路徑**完全不檢查**。
   ```
   # 範例專案與教學用資料
   demo/
   docs/examples/
   ```

### 範例輸出

```
[error] .env
       .env file is tracked by git (adding it to .gitignore now will not untrack it). Run: git rm --cached .env and rotate any exposed secrets.
[warn]  .env
       .env file is not covered by .dockerignore and may be copied into the image by COPY . .
[error] src/a.js:1
       Possible GitHub Token (ghp_…****) hard-coded in source.
```

輸出訊息為英文。找到的金鑰只會顯示前 4 個字元，不會完整印出。

### 放進 CI 或 git hook

```bash
# package.json
"scripts": { "check:secrets": "echeck --strict" }
```

## 當作函式庫使用

```js
const { check, fix } = require("echeck-cli");

const result = check("./my-project", { scan: true });
console.log(result.findings);

if (result.findings.length > 0) {
  const added = fix("./my-project", result); // 回傳新增的規則
}
```

`check()` 回傳 `{ root, filesChecked, filesScanned, skipped, sensitiveFiles, findings }`，
選項：`{ scan: true, scanTests: false }`。
每個 finding 包含 `severity`、`code`、`file`、`message`，內容掃描另有 `line`。

## 限制

- 只讀取專案根目錄的 `.gitignore`（與 `.git/info/exclude`），不處理子目錄中的 `.gitignore`。
- 內容掃描是用正規表達式比對常見格式，可能有漏報或誤報，不能取代專業的 secret 掃描工具。
- `--fix` 只會「新增」規則，不會幫你執行 `git rm --cached`，也不會輪替已外洩的金鑰。
- 如果金鑰已經被推上遠端，光是補 `.gitignore` 不夠，請立刻更換該金鑰。

## 開發

```bash
npm test   # 使用 node:test，需要 Node.js 18+
```

## 授權

MIT
