from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time

from .common import now

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('admin','administrative','student','teacher')),
 full_name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS courses (
 id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 teacher_id INTEGER NOT NULL REFERENCES users(id), credits INTEGER NOT NULL CHECK(credits BETWEEN 0 AND 10),
 capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 1000),
 weekday INTEGER NOT NULL CHECK(weekday BETWEEN 1 AND 7),
 start_period INTEGER NOT NULL CHECK(start_period BETWEEN 1 AND 12),
 end_period INTEGER NOT NULL CHECK(end_period BETWEEN start_period AND 12), room TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS enrollments (
 id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id),
 course_id INTEGER NOT NULL REFERENCES courses(id), created_at TEXT NOT NULL,
 UNIQUE(student_id,course_id)
);
CREATE TABLE IF NOT EXISTS leave_requests (
 id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id),
 start_date TEXT NOT NULL, end_date TEXT NOT NULL CHECK(end_date >= start_date), reason TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 reviewed_by INTEGER REFERENCES users(id), reviewed_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_logs (
 id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), action TEXT NOT NULL,
 target TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_id);
CREATE INDEX IF NOT EXISTS idx_leave_student ON leave_requests(student_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
"""

SEED_USERS = [
    ("admin", "admin123", "admin", "系統管理員"),
    ("office", "office123", "administrative", "教務行政"),
    ("student1", "student123", "student", "王小明"),
    ("student2", "student123", "student", "陳小華"),
    ("teacher1", "teacher123", "teacher", "林老師"),
]


class Database:
    def __init__(self, path):
        self.path = Path(path).resolve()

    @contextmanager
    def connection(self, write=False):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            if write:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        from .auth import hash_password
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'").fetchone()
            if tables and "start_period" not in {r[1] for r in conn.execute("PRAGMA table_info(courses)")}:
                raise RuntimeError("舊資料庫結構不相容，請備份舊檔並以新的 --db 路徑啟動")
            conn.executescript(SCHEMA)
        with self.connection(write=True) as conn:
            if conn.execute("SELECT 1 FROM metadata WHERE key='seeded'").fetchone():
                return
            if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise RuntimeError("未初始化的資料庫已有使用者，請指定新的 --db 路徑")
            for username, password, role, name in SEED_USERS:
                conn.execute("INSERT INTO users(username,password_hash,role,full_name) VALUES(?,?,?,?)",
                             (username, hash_password(password), role, name))
            teacher = conn.execute("SELECT id FROM users WHERE username='teacher1'").fetchone()[0]
            for code, name, credits, capacity, day, start, end, room in [
                ("CS101", "程式設計", 3, 40, 1, 1, 3, "A101"),
                ("DB201", "資料庫系統", 3, 35, 3, 3, 5, "B202"),
                ("ENG101", "學術英文", 2, 50, 5, 1, 2, "C303"),
            ]:
                conn.execute("INSERT INTO courses(code,name,teacher_id,credits,capacity,weekday,start_period,end_period,room) VALUES(?,?,?,?,?,?,?,?,?)",
                             (code, name, teacher, credits, capacity, day, start, end, room))
            student = conn.execute("SELECT id FROM users WHERE username='student2'").fetchone()[0]
            conn.execute("INSERT INTO enrollments(student_id,course_id,created_at) VALUES(?,?,?)", (student, 2, now()))
            conn.execute("INSERT INTO leave_requests(student_id,start_date,end_date,reason,created_at) VALUES(?,?,?,?,?)",
                         (student, "2026-10-05", "2026-10-05", "回診（示範資料）", now()))
            conn.executemany("INSERT INTO settings(key,value) VALUES(?,?)",
                             [("school_name", "校務系統"), ("semester", "115 學年度第一學期"), ("enrollment_open", "true")])
            conn.execute("INSERT INTO metadata VALUES('seeded','1')")

    def backup(self):
        directory = self.path.parent / "backups"
        directory.mkdir(exist_ok=True)
        target = directory / f"school-{time.time_ns()}.db"
        with self.connection() as source:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()
        return target
