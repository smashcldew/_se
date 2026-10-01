import re
from datetime import date, datetime, timezone

ROLES = ("admin", "administrative", "student", "teacher")


class APIError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc).isoformat()


def text(data, key, maximum=200, minimum=1):
    value = data.get(key)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise APIError(f"{key} 必須為 {minimum}～{maximum} 字元")
    return value.strip()


def integer(data, key, minimum=1, maximum=1_000_000):
    value = data.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise APIError(f"{key} 必須為 {minimum}～{maximum} 的整數")
    return value


def date_value(data, key):
    value = text(data, key, 10, 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise APIError(f"{key} 格式必須為 YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise APIError(f"{key} 日期不存在") from None


def require_role(user, *roles):
    if user["role"] not in roles:
        raise APIError("權限不足", 403)


def audit(conn, user_id, action, target):
    conn.execute("INSERT INTO audit_logs(user_id,action,target,created_at) VALUES(?,?,?,?)",
                 (user_id, action, str(target), now()))
