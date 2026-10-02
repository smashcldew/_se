from __future__ import annotations

import argparse
from decimal import Decimal

from .indicators import moving_averages
from .providers import DataProviderError, StockProvider, clear_cache
from .tables import format_table, leaderboard_rows


def _money(value: Decimal | None) -> str:
    return "-" if value is None else f"{value:,.2f}"


def _provider() -> StockProvider:
    return StockProvider()


def quote(args: argparse.Namespace) -> None:
    provider = _provider()
    item = provider.get_quote(args.symbol, args.refresh)
    history = provider.history(args.symbol, months=3, refresh=args.refresh)
    averages = moving_averages(history)
    print(f"{item.symbol} {item.name}（{item.market}）")
    print(f"收盤：{_money(item.close)}  漲跌：{_money(item.change)}  漲跌幅：{_money(item.change_percent)}%")
    print(f"成交量：{item.volume:,} 股")
    print("  ".join(f"MA{key}：{_money(value)}" for key, value in averages.items()))


def history(args: argparse.Namespace) -> None:
    bars = _provider().history(args.symbol, args.months, args.refresh)
    if not bars:
        raise DataProviderError(f"沒有 {args.symbol} 的可用日線資料")
    print("日期        開盤    最高    最低    收盤       成交量")
    for bar in bars[-args.limit:]:
        print(f"{bar.trade_date:%Y-%m-%d}  {bar.open:>6}  {bar.high:>6}  {bar.low:>6}  {bar.close:>6}  {bar.volume:>12,}")
    print("  ".join(f"MA{key}：{_money(value)}" for key, value in moving_averages(bars).items()))


def leaderboard(args: argparse.Namespace) -> None:
    rows = _provider().leaderboard_quotes(args.refresh)
    if args.by == "volume":
        rows.sort(key=lambda row: row.volume, reverse=True)
        title = "成交量"
    else:
        rows = [row for row in rows if row.change_percent is not None]
        rows.sort(key=lambda row: row.change_percent or Decimal("0"), reverse=True)
        title = "漲跌幅"
    print(f"台股上市個股 {title} 前 {args.limit} 名")
    print(format_table(["排名", "代號", "名稱", "收盤", "漲跌幅", "成交量", "行業"],
                       leaderboard_rows(rows[:args.limit])))


def report(args: argparse.Namespace) -> None:
    provider = _provider()
    item = provider.get_quote(args.symbol, args.refresh)
    bars = provider.history(args.symbol, months=6, refresh=args.refresh)
    averages = moving_averages(bars)
    print(f"# {item.symbol} {item.name} 個股評估報告")
    print(f"\n## 市場資料\n- 市場：{item.market}\n- 收盤：{_money(item.close)}\n- 當日漲跌幅：{_money(item.change_percent)}%\n- 成交量：{item.volume:,} 股")
    print("\n## 技術面")
    for period, value in averages.items():
        relation = "資料不足" if value is None else ("收盤高於均線" if item.close > value else "收盤低於均線")
        print(f"- MA{period}：{_money(value)}（{relation}）")
    print("\n## 新聞情緒\n- 尚未接入新聞資料來源，因此未產生情緒結論。")
    print("\n## 免責聲明\n- 本報告僅為公開資料與規則式技術指標的整理，不構成投資建議。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stockfollower", description="台股追蹤 CLI（研究用途）")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("quote", quote), ("history", history), ("report", report)):
        command = sub.add_parser(name)
        command.add_argument("symbol", help="四位數股票代號，例如 2330")
        command.add_argument("--refresh", action="store_true", help="略過本機快取並重新下載")
        if name == "history":
            command.add_argument("--months", type=int, default=6)
            command.add_argument("--limit", type=int, default=20)
        command.set_defaults(handler=handler)
    board = sub.add_parser("leaderboard")
    board.add_argument("--by", choices=("volume", "change"), default="volume")
    board.add_argument("--limit", type=int, default=50)
    board.add_argument("--refresh", action="store_true")
    board.set_defaults(handler=leaderboard)
    gui = sub.add_parser("gui", help="開啟桌面視窗介面")
    gui.set_defaults(handler=launch_gui)
    return parser


def launch_gui(args: argparse.Namespace) -> None:
    from .gui import launch

    launch()


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command != "gui":
            clear_cache()
        args.handler(args)
    except (DataProviderError, ValueError) as exc:
        raise SystemExit(f"錯誤：{exc}")


if __name__ == "__main__":
    main()
