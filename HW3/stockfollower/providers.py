from __future__ import annotations

import json
import ssl
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi

from .models import DailyBar, Quote

TWSE_OPENAPI = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_HISTORY = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
CACHE_DIR = Path("data/cache")


class DataProviderError(RuntimeError):
    pass


def _get_json(url: str, params: dict[str, str] | None = None) -> object:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "StockFollower/0.1 (research CLI)"})
    try:
        # 使用 certifi 的根憑證，避免某些 Windows/Python 組合的系統憑證問題。
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=20, context=context) as response:
            return json.loads(response.read().decode("utf-8-sig"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DataProviderError(f"無法取得官方資料：{exc}") from exc


def _number(value: object) -> Decimal:
    text = str(value).strip().replace(",", "").replace("--", "")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise DataProviderError(f"無法解析數值：{value!r}") from exc


def _roc_date(value: str) -> date:
    year, month, day = (int(item) for item in value.split("/"))
    return date(year + 1911, month, day)


class TwseProvider:
    """TWSE 上市股票的公開資料提供者。"""

    def latest_quotes(self, refresh: bool = False) -> list[Quote]:
        cache_file = CACHE_DIR / f"twse_quotes_{date.today():%Y%m%d}.json"
        if cache_file.exists() and not refresh:
            rows = json.loads(cache_file.read_text(encoding="utf-8"))
        else:
            rows = _get_json(TWSE_OPENAPI)
            if not isinstance(rows, list):
                raise DataProviderError("官方報價資料格式不正確")
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

        quotes: list[Quote] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("Code", "")).strip()
            # 排除 ETF、權證等；個股代號通常為 4 碼數字。
            if not (len(symbol) == 4 and symbol.isdigit()):
                continue
            close = _number(row.get("ClosingPrice", ""))
            change = _number(row.get("Change", "")) if str(row.get("Change", "")).strip() else None
            sign = str(row.get("Change", "")).strip()
            if str(row.get("UpDown", "")).strip() == "-" and change is not None:
                change = -abs(change)
            previous = close - change if change is not None else None
            percent = (change / previous * 100) if previous not in (None, Decimal("0")) else None
            quotes.append(Quote(symbol, str(row.get("Name", "")), "TWSE", close, int(_number(row.get("TradeVolume", 0))), change, percent))
        return quotes

    def history(self, symbol: str, months: int = 6, refresh: bool = False) -> list[DailyBar]:
        if not (symbol.isdigit() and len(symbol) == 4):
            raise ValueError("股票代號須為四位數字，例如 2330")
        today = date.today()
        result: dict[date, DailyBar] = {}
        for offset in range(months):
            year = today.year + ((today.month - 1 - offset) // 12)
            month = (today.month - 1 - offset) % 12 + 1
            stamp = f"{year}{month:02}01"
            cache_file = CACHE_DIR / f"twse_{symbol}_{stamp}.json"
            if cache_file.exists() and not refresh:
                payload = json.loads(cache_file.read_text(encoding="utf-8"))
            else:
                payload = _get_json(TWSE_HISTORY, {"date": stamp, "stockNo": symbol, "response": "json"})
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            if not isinstance(payload, dict) or payload.get("stat") != "OK":
                continue
            for row in payload.get("data", []):
                if len(row) < 9:
                    continue
                bar_date = _roc_date(row[0])
                result[bar_date] = DailyBar(bar_date, _number(row[3]), _number(row[4]), _number(row[5]), _number(row[6]), int(_number(row[1])), _number(row[8]))
        return [result[key] for key in sorted(result)]
