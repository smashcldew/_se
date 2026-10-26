# 開發驗證紀錄

## 2026-07-13：CLI 功能驗證

驗證位置：`D:\stockfollower`

### 結果

| 項目 | 指令 | 結果 |
| --- | --- | --- |
| 單一報價 | `python -m stockfollower quote 2330` | 通過：顯示台積電（2330）收盤 2,415.00、跌幅 -2.03%、成交量與 MA5/10/20。 |
| 歷史行情 | `python -m stockfollower history 2330 --months 6` | 通過：顯示近期歷史行情，以及 MA5/10/20/60。 |
| 成交量排行 | `python -m stockfollower leaderboard --by volume --limit 3` | 通過：顯示前三名為 2409 友達、3481 群創、2344 華邦電。 |
| 個股報告 | `python -m stockfollower report 2330` | 通過：產生市場資料、均線技術面、新聞情緒提示與免責聲明。 |
| 自動化測試 | `python -m pytest -q` | 未執行：目前 Python 環境未安裝 `pytest`，錯誤為 `No module named pytest`。 |

### 資料來源與範圍

- CLI 成功讀取既有的 `data/cache/` 快取資料。
- 本次未使用 `--refresh`，因此僅驗證現有快取與輸出流程，不代表即時市場資料可用。

### 後續建議

安裝開發測試相依後再執行：`python -m pip install pytest`，接著以 `python -m pytest -q` 驗證單元測試。

## 2026-07-13：桌面視窗入口

- 新增 `stockfollower gui` 指令，使用 Python 內建 Tkinter 開啟桌面視窗，不需新增執行期相依套件。
- 視窗提供股票代號輸入、即時報價、歷史行情、個股報告與成交量排行；資料讀取沿用原有的 `TwseProvider` 與快取機制。
- 視窗新增「漲幅排行」與「跌幅排行」，分別列出當日漲幅、跌幅最高的前 20 檔股票。
- 為縮減控制列寬度，三種排行整合為「排行榜」下拉選單（成交量、漲幅、跌幅）與單一查詢按鈕。
- 將「即時報價」更名為「最新收盤」，避免誤認為盤中即時行情；歷史行情新增 Matplotlib 收盤價折線圖（橫軸日期、縱軸價格）。
- 補上 setuptools 套件清單，避免安裝時將 `data/` 誤判為 Python 套件。
- 歷史圖新增時間軸下拉選單：日、週、月、年；週／月／年分別採各期間最後一個交易日的收盤價。
- 修正歷史圖時間軸選項未在歷史行情查詢中讀取，導致 `NameError` 的問題。
- 圖表標題與座標軸改用 Windows 微軟正黑體，修正 Matplotlib 預設字型缺少中文字形的警告。
- 歷史價格圖改為嵌入主視窗，下拉選單保留日／週／月／年取樣；查詢區間改為可調整的 1–24 個月，預設 3 個月。
- 歷史圖升級為 K 線圖，加入 MA5（藍色）與 MA10（黃色）；週／月／年模式會先彙整 OHLC，再依該週期計算均線。
- 歷史行情查詢改為只顯示內嵌 K 線與均線圖，不再顯示文字行情表；其他功能的文字輸出維持不變。
- K 線 X 軸改為連續交易日序號，週末與休市日不再產生空白間距；刻度仍顯示實際交易日期。

## 2026-10-26：移除 CLI、僅保留 GUI 並簡化程式碼

- 移除 `stockfollower/cli.py`，`python -m stockfollower` 直接開啟桌面視窗；`pyproject.toml` 的 console script 改指向 `stockfollower.gui:launch`。
- 清除 GUI 內已無按鈕使用的 `show_quote`、`show_report` 與 `_show_text_output`；`_show_result` 直接負責顯示報告區。
- 統一錯誤處理：`_run` 的個股與排行榜錯誤皆走 `_show_error`，不再重複 messagebox 邏輯。
- 將 `_chart_month_starts`、`_chart_year_starts`、`_chart_day_ticks` 合併為單一的 `_chart_starts(dates, key)`。
- `tables.py` 移除僅供 CLI 文字輸出使用的 `format_table` 與 `display_width`，保留 GUI 使用的 `leaderboard_rows`。
- 移除 `providers.py` TWSE 報價中未使用的 `sign` 變數。
- 移除對應的 CLI 測試；排行榜欄位對齊測試改為驗證 `leaderboard_rows` 的七欄輸出。驗證：`python -m pytest -q` 共 30 筆測試通過。

## 2026-10-26：新增 SQLite 資料庫持久化股價

- 新增 `stockfollower/storage.py` 的 `PriceStore`，以 SQLite 保存股價，資料庫檔為 `data/stockfollower.db`，不受啟動時快取清除影響。
- 兩張表：`quotes`（代號、名稱、市場、日期、收盤、漲跌、漲跌幅、交易量、行業）與 `daily_bars`（日線 OHLC）；皆以 `(symbol, trade_date)` 為主鍵並採 upsert，價格以字串保存以保留 Decimal 精度。
- 每個操作各自開啟連線，避免 GUI 背景執行緒共用連線的問題；資料庫錯誤包裝為 `StorageError`。
- GUI 於個股搜尋時自動寫入：存入當日報價與整段日線（以最後交易日為日期）；排行榜查詢不寫入資料庫。寫入為最佳努力，失敗不影響畫面顯示。
- 新增 `tests/test_storage.py`（round-trip、upsert、日期分隔、空輸入）與 GUI→DB 整合測試。驗證：`python -m pytest -q` 共 38 筆測試通過。

## 2026-10-26：依查詢日期判斷現場 / 資料庫來源

- 新增 `fetch_log` 表記錄每個代號「上次向 API 抓取的日期」；`PriceStore` 新增 `record_fetch()`／`last_fetch()`、`prices_since()`、`latest_quote()`。
- 個股搜尋邏輯：當天第一次查該代號（或勾 `Refresh cache`）走 API 並存 DB、更新 `fetch_log`；同一天再查同一代號改讀 DB，不再連網；跨日則重新打 API。每個代號各自記錄。
- 狀態列顯示資料來源：「來源：現場下載」或「來源：資料庫（日期 已更新）」。
- 排行榜維持不進資料庫。
- 新增同日重查讀 DB、`Refresh cache` 強制走 API 的測試。驗證：`python -m pytest -q` 共 39 筆測試通過。

## 2026-10-26：修正排行榜（及個股查詢）只有第一次有反應的問題

- 根因：`_run` 的背景執行緒直接呼叫 `self.root.after(...)`，從工作執行緒操作 Tkinter 並不安全；在 Windows 上常導致第一次之後的 callback 排不進事件迴圈，狀態卡在「Loading...」而看似無反應。
- 修正：工作執行緒只把 `(callback, payload)` 放進執行緒安全的 `queue.Queue`，由主執行緒的 `_poll_results`（啟動時以 `after(50, ...)` 排程、持續輪詢）取出並更新畫面；所有 Tk 操作都回到主執行緒。
- 同步更新兩個以舊 `root.after` 遞送機制撰寫的測試，改為從佇列取出 callback 驗證。驗證：`python -m pytest -q` 共 39 筆測試通過；另以真實事件迴圈連點排行榜四次，每次皆正常觸發與更新。

## 2026-10-26：新增市場儀表板（dev 分支）

- 新增 `stockfollower/dashboard.py`：`market_breadth()`（上漲／下跌／平盤、漲停／跌停以 ±9.9% 近似、總量、平均漲跌幅、騰落比）與 `industry_changes()`（各產業平均漲跌幅、依強弱排序）；皆為純函式，用既有的 TWSE 全市場報價計算，不需新資料來源。
- GUI 於排行榜區新增「市場儀表板」按鈕，另開 Toplevel 顯示 KPI 卡 + 各產業平均漲跌幅長條圖（紅漲綠跌）；沿用 provider 與主執行緒佇列機制，重複點擊重用同一視窗。
- 中文字型以 `_cjk_font()` 自動挑選系統可用字型（微軟正黑體等），找不到則回退預設。
- 新增 `tests/test_dashboard.py`（breadth 計數／邊界、產業平均與排序、GUI 接線）。驗證：`python -m pytest -q` 共 44 筆測試通過；另以真實事件迴圈煙霧測試儀表板開啟與重用，無崩潰。
