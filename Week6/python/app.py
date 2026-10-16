import os
import re
from collections import Counter

import psycopg
from flask import Flask, jsonify

app = Flask(__name__)


def connect_db():
    return psycopg.connect(
        host=os.getenv("PGHOST", "db"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "docker_demo"),
        user=os.getenv("PGUSER", "demo"),
        password=os.getenv("PGPASSWORD", "demo_password"),
        connect_timeout=3,
    )


@app.get("/health")
def health():
    try:
        with connect_db() as connection:
            connection.execute("SELECT 1")
        return jsonify(status="ok", service="python", database="connected")
    except Exception:
        return jsonify(status="error", service="python", database="unavailable"), 503


@app.get("/stats")
def stats():
    try:
        with connect_db() as connection:
            rows = connection.execute("SELECT message FROM messages ORDER BY created_at DESC LIMIT 500").fetchall()
        text = " ".join(row[0] for row in rows)
        words = re.findall(r"[\w'-]+", text.lower(), flags=re.UNICODE)
        return jsonify(
            message_count=len(rows),
            average_length=round(sum(len(row[0]) for row in rows) / len(rows), 1) if rows else 0,
            top_words=[{"word": word, "count": count} for word, count in Counter(words).most_common(8)],
        )
    except Exception:
        return jsonify(error="資料庫暫時無法使用"), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
