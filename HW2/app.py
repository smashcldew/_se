"""Entry point: python app.py [--port 8000] [--cert CERT --key KEY]."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import ssl

from school.database import Database
from school.server import create_server

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="校務系統")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "school.db")
    parser.add_argument("--cert", type=Path)
    parser.add_argument("--key", type=Path)
    parser.add_argument("--backup", action="store_true", help="備份資料庫後結束")
    args = parser.parse_args()
    if bool(args.cert) != bool(args.key):
        parser.error("--cert 與 --key 必須同時指定")
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(log_dir / "school.log", maxBytes=1_000_000,
                            backupCount=3, encoding="utf-8"),
    ])
    database = Database(args.db)
    database.initialize()
    if args.backup:
        print(database.backup())
        return
    server = create_server(database, args.host, args.port, secure=bool(args.cert))
    if args.cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(args.cert, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    logging.info("開啟 %s://%s:%s", "https" if args.cert else "http", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("伺服器停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
