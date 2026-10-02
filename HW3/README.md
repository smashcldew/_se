# StockFollower（台股追蹤 CLI）

本專案是台股研究與追蹤工具，現階段以命令列操作。它使用證交所（TWSE）與櫃買中心（TPEx）的公開資料，提供日線、均線、排行榜與基礎評估報告。

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

首次查詢日線會向官方公開 API 下載資料並快取在 `data/cache/`；可用 `--refresh` 強制更新。

## 指令

| 指令 | 用途 |
| --- | --- |
| `quote 股票代號` | 顯示最近一個交易日報價與均線 |
| `history 股票代號` | 顯示最近日線與均線 |
| `leaderboard` | 依成交量或漲跌幅列出前 50 名 |
| `report 股票代號` | 輸出個股評估報告 |

## 下一階段

- 接入合規新聞來源，建立摘要與情緒分析流程。
- 儲存追蹤清單與排程更新。
- 製作網頁或桌面介面。
