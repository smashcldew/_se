from dataclasses import dataclass, field
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlparse

from . import admin, auth, courses, enrollment, extensions, leave
from .common import APIError, require_role

STATIC = Path(__file__).resolve().parent.parent / "static"


@dataclass
class Context:
    db: object
    user: dict | None
    data: dict
    query: dict
    token: str
    params: dict = field(default_factory=dict)
    cookie: str | None = None


class Router:
    def __init__(self):
        self.routes = []

    def add(self, method, path, handler, roles=None, public=False):
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[1-9][0-9]*)", path)
        self.routes.append((method, re.compile("^" + pattern + "$"), handler, roles, public))

    def dispatch(self, method, path, context):
        allowed = []
        for route_method, pattern, handler, roles, public in self.routes:
            match = pattern.fullmatch(path)
            if not match:
                continue
            allowed.append(route_method)
            if route_method != method:
                continue
            if not public:
                context.user = auth.authenticate(context.db, context.token)
                if roles:
                    require_role(context.user, *roles)
            context.params = {k: int(v) for k, v in match.groupdict().items()}
            return handler(context)
        raise APIError("此路徑不支援該 HTTP 方法" if allowed else "找不到 API", 405 if allowed else 404)


def build_router(secure=False):
    router = Router()

    def login(context):
        result = auth.login(context.db, context.data)
        context.cookie = f"session={result['token']}; Path=/; HttpOnly; SameSite=Lax; Max-Age={auth.SESSION_SECONDS}" + ("; Secure" if secure else "")
        return result

    def logout(context):
        result = auth.logout(context.db, context.token)
        context.cookie = "session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0" + ("; Secure" if secure else "")
        return result

    router.add("POST", "/api/login", login, public=True)
    router.add("POST", "/api/logout", logout)
    router.add("GET", "/api/me", lambda c: c.user)
    router.add("GET", "/api/settings", lambda c: admin.settings(c.db))
    router.add("PUT", "/api/settings", lambda c: admin.save_settings(c.db, c.user, c.data), roles=("admin",))
    router.add("GET", "/api/users", lambda c: auth.list_users(c.db, c.user), roles=("admin",))
    router.add("POST", "/api/users", lambda c: auth.save_user(c.db, c.user, c.data), roles=("admin",))
    router.add("PUT", "/api/users/{id}", lambda c: auth.save_user(c.db, c.user, c.data, c.params["id"]), roles=("admin",))
    router.add("GET", "/api/teachers", lambda c: auth.list_users(c.db, c.user, True))
    router.add("GET", "/api/courses", lambda c: courses.list_courses(c.db, c.user, c.query.get("q", [""])[0]))
    router.add("POST", "/api/courses", lambda c: courses.save_course(c.db, c.user, c.data), roles=("admin", "administrative"))
    router.add("PUT", "/api/courses/{id}", lambda c: courses.save_course(c.db, c.user, c.data, c.params["id"]), roles=("admin", "administrative"))
    router.add("DELETE", "/api/courses/{id}", lambda c: courses.delete_course(c.db, c.user, c.params["id"]), roles=("admin", "administrative"))
    router.add("POST", "/api/enroll", lambda c: enrollment.enroll(c.db, c.user, c.data), roles=("student",))
    router.add("DELETE", "/api/enroll/{id}", lambda c: enrollment.withdraw(c.db, c.user, c.params["id"]), roles=("student",))
    router.add("GET", "/api/schedule", lambda c: enrollment.schedule(c.db, c.user))
    router.add("GET", "/api/leave", lambda c: leave.list_requests(c.db, c.user))
    router.add("POST", "/api/leave", lambda c: leave.submit(c.db, c.user, c.data), roles=("student",))
    router.add("POST", "/api/leave/{id}/review", lambda c: leave.review(c.db, c.user, c.data, c.params["id"]), roles=("admin", "administrative", "teacher"))
    router.add("GET", "/api/audit", lambda c: admin.logs(c.db, c.user), roles=("admin",))
    router.add("POST", "/api/backup", lambda c: admin.backup(c.db, c.user), roles=("admin",))
    extensions.register(router)
    return router


def create_server(database, host="127.0.0.1", port=8000, secure=False):
    router = build_router(secure)

    class Handler(BaseHTTPRequestHandler):
        server_version = "SchoolPortal/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, format, *args):
            logging.info("HTTP %s %s", self.command, urlparse(self.path).path)

        def response(self, content, status=200, mime="application/json; charset=utf-8", cookie=None):
            if not isinstance(content, bytes):
                content = json.dumps(content, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if secure:
                self.send_header("Strict-Transport-Security", "max-age=31536000")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(content)

        def read_body(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise APIError("Content-Length 不合法") from None
            if not 0 <= size <= 65536:
                raise APIError("請求內容過大", 413)
            if size and self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise APIError("請使用 application/json", 415)
            try:
                data = json.loads(self.rfile.read(size) or b"{}")
            except (ValueError, UnicodeDecodeError):
                raise APIError("JSON 格式錯誤") from None
            if not isinstance(data, dict):
                raise APIError("JSON 必須為物件")
            return data

        def handle_request(self):
            path = urlparse(self.path).path
            try:
                if not path.startswith("/api/"):
                    files = {"/": ("index.html", "text/html"), "/index.html": ("index.html", "text/html"),
                             "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
                    if self.command != "GET" or path not in files:
                        raise APIError("找不到頁面", 404)
                    filename, mime = files[path]
                    return self.response((STATIC / filename).read_bytes(), mime=mime + "; charset=utf-8")
                cookie = SimpleCookie()
                try:
                    cookie.load(self.headers.get("Cookie", ""))
                except CookieError:
                    raise APIError("Cookie 格式錯誤") from None
                authorization = self.headers.get("Authorization", "")
                token = authorization[7:] if authorization.startswith("Bearer ") else (cookie["session"].value if "session" in cookie else "")
                if self.command != "GET":
                    origin = self.headers.get("Origin")
                    if origin and origin != ("https" if secure else "http") + "://" + self.headers.get("Host", ""):
                        raise APIError("不允許跨來源操作", 403)
                    if self.headers.get("Sec-Fetch-Site") == "cross-site":
                        raise APIError("不允許跨來源操作", 403)
                    if "session" in cookie and not authorization.startswith("Bearer ") and self.headers.get("X-Requested-With") != "SchoolPortal":
                        raise APIError("缺少操作驗證標頭", 403)
                data = self.read_body() if self.command != "GET" else {}
                context = Context(database, None, data, parse_qs(urlparse(self.path).query), token)
                result = router.dispatch(self.command, path, context)
                status = 201 if self.command == "POST" and path in ("/api/users", "/api/courses", "/api/enroll", "/api/leave") else 200
                self.response(result, status, cookie=context.cookie)
            except APIError as error:
                self.response({"error": str(error)}, error.status)
            except sqlite3.IntegrityError:
                self.response({"error": "資料重複或違反資料庫限制"}, 409)
            except sqlite3.OperationalError:
                logging.exception("資料庫操作失敗")
                self.response({"error": "資料庫忙碌，請稍後再試"}, 503)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                logging.warning("用戶端中斷連線")
            except Exception:
                logging.exception("伺服器處理請求失敗")
                self.response({"error": "伺服器發生錯誤，請查看伺服器紀錄"}, 500)

        do_GET = handle_request
        do_POST = handle_request
        do_PUT = handle_request
        do_DELETE = handle_request

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
