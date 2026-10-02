from __future__ import annotations

import json
import ssl
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi

from .models import DailyBar, Quote
from .industries import UNKNOWN_INDUSTRY, industry_name

TWSE_OPENAPI = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_HISTORY = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
TWSE_COMPANIES = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_OPENAPI = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
TPEX_HISTORY = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
CACHE_DIR = Path("data/cache")


class DataProviderError(RuntimeError):
    pass


def clear_cache() -> None:
    """Remove this application's market cache files at startup."""
    try:
        for pattern in ("twse_*.json", "tpex_*.json"):
            for cache_file in CACHE_DIR.glob(pattern):
                if cache_file.is_file():
                    cache_file.unlink(missing_ok=True)
    except OSError as exc:
        raise DataProviderError(f"無法清除快取：{exc}") from exc


def _get_json(url: str, params: dict[str, str] | None = None) -> object:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "StockFollower/0.1 (research CLI)"})
    try:
        # 使用 certifi 的根憑證，避免某些 Windows/Python 組合的系統憑證問題。
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=20, context=context) as response:
            return json.loads(response.read().decode("utf-8-sig"))
    except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
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

    def company_industries(self, refresh: bool = False) -> dict[str, str]:
        cache_file = CACHE_DIR / "twse_industries.json"
        if cache_file.exists() and not refresh:
            rows = json.loads(cache_file.read_text(encoding="utf-8"))
        else:
            rows = _get_json(TWSE_COMPANIES)
            if not isinstance(rows, list) or not rows or not all(
                isinstance(row, dict) and "公司代號" in row and "產業別" in row for row in rows
            ):
                raise DataProviderError("官方公司產業資料格式不正確")
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return {str(row["公司代號"]).strip(): industry_name(row["產業別"]) for row in rows}

    def leaderboard_quotes(self, refresh: bool = False) -> list[Quote]:
        quotes = self.latest_quotes(refresh)
        industries = self.company_industries(refresh)
        return [replace(row, industry=industries.get(row.symbol, UNKNOWN_INDUSTRY)) for row in quotes]

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
                change_text = str(row[7]).strip()
                change = None if not change_text or change_text == "--" or change_text.startswith("X") else _number(change_text)
                result[bar_date] = DailyBar(bar_date, _number(row[3]), _number(row[4]), _number(row[5]), _number(row[6]), int(_number(row[1])), change)
        return [result[key] for key in sorted(result)]


class TpexProvider:
    """TPEx 上櫃股票的公開資料提供者。"""

    def latest_quotes(self, refresh: bool = False) -> list[Quote]:
        cache_file = CACHE_DIR / f"tpex_quotes_{date.today():%Y%m%d}.json"
        if cache_file.exists() and not refresh:
            rows = json.loads(cache_file.read_text(encoding="utf-8"))
        else:
            rows = _get_json(TPEX_OPENAPI)
            if not isinstance(rows, list) or not rows or not all(
                isinstance(row, dict) and "SecuritiesCompanyCode" in row and "Close" in row for row in rows
            ):
                raise DataProviderError("櫃買中心報價資料格式不正確，請稍後重試")
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        quotes = []
        for row in rows:
            symbol = str(row["SecuritiesCompanyCode"]).strip()
            if not (symbol.isascii() and symbol.isdigit() and len(symbol) == 4):
                continue
            close_text = str(row["Close"]).strip()
            if not close_text or not close_text.strip("-"):
                continue
            close = _number(close_text)
            change_text = str(row.get("Change", "")).strip()
            change = None if not change_text.strip("-") or change_text.startswith(("X", "除")) else _number(change_text)
            previous = close - change if change is not None else None
            percent = change / previous * 100 if previous not in (None, Decimal("0")) else None
            quotes.append(Quote(symbol, str(row.get("CompanyName", "")).strip(), "TPEx", close,
                                int(_number(row.get("TradingShares", 0))), change, percent))
        return quotes

    def history(self, symbol: str, months: int = 6, refresh: bool = False) -> list[DailyBar]:
        if not (symbol.isascii() and symbol.isdigit() and len(symbol) == 4):
            raise ValueError("股票代號須為四位數字，例如 6274")
        if months <= 0:
            raise ValueError("months 必須大於 0")
        today = date.today()
        result: dict[date, DailyBar] = {}
        for offset in range(months):
            year = today.year + ((today.month - 1 - offset) // 12)
            month = (today.month - 1 - offset) % 12 + 1
            cache_file = CACHE_DIR / f"tpex_{symbol}_{year}{month:02}01.json"
            if cache_file.exists() and not refresh:
                payload = json.loads(cache_file.read_text(encoding="utf-8"))
            else:
                payload = _get_json(TPEX_HISTORY, {"code": symbol, "date": f"{year}/{month:02}/01", "response": "json"})
                if not isinstance(payload, dict) or str(payload.get("stat", "")).lower() != "ok":
                    raise DataProviderError("櫃買中心歷史行情回應異常，請稍後重試")
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            for table in payload.get("tables", []):
                for row in table.get("data", []):
                    if len(row) < 9:
                        continue
                    trade_date = _roc_date(row[0])
                    change_text = str(row[7]).strip()
                    change = None if not change_text.strip("-") or change_text.startswith(("X", "除")) else _number(change_text)
                    result[trade_date] = DailyBar(trade_date, _number(row[3]), _number(row[4]),
                                                _number(row[5]), _number(row[6]),
                                                int(_number(row[1]) * 1000), change)
        return [result[key] for key in sorted(result)]


class StockProvider(TwseProvider):
    """Route individual-stock queries to TWSE or TPEx; rankings remain TWSE."""

    def __init__(self) -> None:
        self._markets: dict[str, str] = {}
        self._tpex = TpexProvider()

    def get_quote(self, symbol: str, refresh: bool = False) -> Quote:
        if not (symbol.isascii() and symbol.isdigit() and len(symbol) == 4):
            raise ValueError("股票代號須為四位數字，例如 2330 或 6274")
        for market, quotes in (("TWSE", self.latest_quotes), ("TPEx", self._tpex.latest_quotes)):
            item = next((row for row in quotes(refresh) if row.symbol == symbol), None)
            if item is not None:
                self._markets[symbol] = market
                return item
        raise DataProviderError(f"上市及上櫃市場皆無 {symbol} 的可用收盤報價，請確認代號；興櫃股票尚未支援。")

    def history(self, symbol: str, months: int = 6, refresh: bool = False) -> list[DailyBar]:
        if not (symbol.isascii() and symbol.isdigit() and len(symbol) == 4):
            raise ValueError("股票代號須為四位數字，例如 2330 或 6274")
        market = self._markets.get(symbol)
        if market is None:
            # The historical TPEx endpoint works independently of the large
            # full-market quote download; do not require that download here.
            market = "TWSE" if any(row.symbol == symbol for row in self.latest_quotes(refresh)) else "TPEx"
        if market == "TPEx":
            return self._tpex.history(symbol, months, refresh)
        return super().history(symbol, months, refresh)
