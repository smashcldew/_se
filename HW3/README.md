# StockFollower（台股追蹤 CLI）

本專案是台股研究與追蹤工具，提供 CLI 與桌面 GUI。個股報價、日線、均線及報告支援證交所（TWSE）上市股票與櫃買中心（TPEx）上櫃股票，依代號自動選擇資料來源，例如 `2330` 與 `6274`。排行榜目前涵蓋 TWSE 上市個股。興櫃股票尚未支援。

> 本工具僅供資訊整理與研究輔助，不構成投資建議。公開資料可能延遲、缺漏或修正，使用前請自行核對。

## 快速開始

```powershell
cd D:\stockfollower
python -m stockfollower quote 2330
python -m stockfollower history 2330 --months 6
python -m stockfollower leaderboard --by volume --limit 50
python -m stockfollower report 2330
python -m stockfollower gui
```

每次啟動 CLI 指令或 GUI 時，會先清除 `data/cache/` 中本程式的 `twse_*.json` 與 `tpex_*.json` 快取，再於查詢時向官方公開 API 下載資料。同一次 GUI 使用期間會重用快取；可勾選 `Refresh cache` 強制更新，CLI 也保留 `--refresh` 選項。TPEx 歷史行情的成交量由官方的「張」換算成「股」，精度依來源資料而定。

## 指令

| 指令 | 用途 |
| --- | --- |
| `quote 股票代號` | 顯示最近一個交易日報價與均線 |
| `history 股票代號` | 顯示最近日線與均線 |
| `leaderboard` | 依成交量或漲跌幅列出前 50 名 |
| `report 股票代號` | 輸出個股評估報告 |

排行榜會透過[證交所上市公司基本資料](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)取得產業別，並顯示中文行業名稱。GUI 的 `Show leaderboard` 按鈕下方提供行業篩選，選擇後自動顯示該行業依成交量、漲幅或跌幅排序的前 20 名；選擇「全部行業」可恢復完整市場排行。沒有對應公司資料的個股顯示為「未分類」。行業資料下載失敗時會顯示錯誤，可再次查詢重試。

GUI 左側為個股區（70%），右側為排行榜區（30%），視窗縮放時維持比例。兩區的查詢結果、更新快取選項與狀態各自獨立，排行榜不會覆蓋個股報價、報告或 K 線。排行榜可水平捲動查看完整欄位。

## 下一階段

- 接入合規新聞來源，建立摘要與情緒分析流程。
- 儲存追蹤清單與排程更新。
- 製作網頁或桌面介面。
