import hashlib
import re
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .common import APIError, ROLES, audit, text, require_role

HASHER = PasswordHasher()
SESSION_SECONDS = 8 * 60 * 60


def hash_password(password):
    return HASHER.hash(password)


def password_value(data, minimum=1):
    value = data.get("password")
    if not isinstance(value, str) or not minimum <= len(value) <= 128 or not value.strip():
        raise APIError(f"password 必須為 {minimum}～128 字元")
    # Preserve spaces in secrets instead of silently normalizing them.
    return value


def verify_password(encoded, password):
    try:
        return HASHER.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def public_user(row):
    return {"id": row["id"], "username": row["username"], "role": row["role"],
            "full_name": row["full_name"], "active": bool(row["active"])}


def login(database, data):
    username = text(data, "username", 64)
    password = password_value(data)
    with database.connection(write=True) as conn:
        row = conn.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
        if row is None or not verify_password(row["password_hash"], password):
            raise APIError("帳號或密碼錯誤", 401)
        if HASHER.check_needs_rehash(row["password_hash"]):
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), row["id"]))
        token = secrets.token_urlsafe(32)
        expires = int(time.time()) + SESSION_SECONDS
        conn.execute("DELETE FROM sessions WHERE expires_at<=?", (int(time.time()),))
        conn.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), row["id"], expires))
        audit(conn, row["id"], "login", row["id"])
        return {"token": token, "expires_at": expires, "user": public_user(row)}


def authenticate(database, token):
    if not token:
        raise APIError("請先登入", 403)
    with database.connection() as conn:
        row = conn.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1",
                           (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        if not row:
            raise APIError("登入已失效，請重新登入", 403)
        return public_user(row)


def logout(database, token):
    with database.connection(write=True) as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
    return {"message": "已登出"}


def list_users(database, user, teachers_only=False):
    if not teachers_only:
        require_role(user, "admin")
    with database.connection() as conn:
        rows = conn.execute("SELECT * FROM users WHERE role='teacher' AND active=1 ORDER BY id" if teachers_only else "SELECT * FROM users ORDER BY id").fetchall()
        return [public_user(row) for row in rows]


def save_user(database, user, data, user_id=None):
    require_role(user, "admin")
    username = text(data, "username", 64)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        raise APIError("帳號只能使用英文、數字、底線、點或連字號")
    name = text(data, "full_name", 80)
    role = text(data, "role", 20)
    if role not in ROLES:
        raise APIError("角色不合法")
    active = data.get("active", True)
    if type(active) is not bool:
        raise APIError("active 必須為布林值")
    password = None
    if user_id is None or "password" in data:
        password = hash_password(password_value(data, 8))
    with database.connection(write=True) as conn:
        if user_id is None:
            if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                raise APIError("帳號已存在", 409)
            uid = conn.execute("INSERT INTO users(username,password_hash,role,full_name,active) VALUES(?,?,?,?,?)",
                               (username, password, role, name, active)).lastrowid
        else:
            old = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not old:
                raise APIError("使用者不存在", 404)
            if user_id == user["id"] and (role != "admin" or not active):
                raise APIError("不可停用自己的管理員權限", 409)
            if old["role"] != role and conn.execute("SELECT 1 FROM courses WHERE teacher_id=? UNION SELECT 1 FROM enrollments WHERE student_id=? UNION SELECT 1 FROM leave_requests WHERE student_id=?", (user_id, user_id, user_id)).fetchone():
                raise APIError("使用者已有校務紀錄，無法變更角色", 409)
            if conn.execute("SELECT 1 FROM users WHERE username=? AND id<>?", (username, user_id)).fetchone():
                raise APIError("帳號已存在", 409)
            conn.execute("UPDATE users SET username=?,password_hash=?,role=?,full_name=?,active=? WHERE id=?",
                         (username, password or old["password_hash"], role, name, active, user_id))
            if password or role != old["role"] or not active:
                conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            uid = user_id
        audit(conn, user["id"], "save_user", uid)
        return public_user(conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
