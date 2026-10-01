from pathlib import Path
import tempfile
import threading
import unittest
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from school import auth
from school.database import Database
from school.server import create_server


class DatabaseCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hw2-test-")
        self.addCleanup(self.temp.cleanup)
        self.db = Database(Path(self.temp.name) / "school.db")
        self.db.initialize()
        with self.db.connection() as conn:
            self.users = {row["username"]: auth.public_user(row) for row in conn.execute("SELECT * FROM users")}


class ServerCase(DatabaseCase):
    def setUp(self):
        super().setUp()
        self.start_server()
        self.addCleanup(self.stop_server)

    def start_server(self):
        self.server = create_server(self.db, port=0)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path, method="GET", data=None, token=None, headers=None):
        body = json.dumps(data).encode() if data is not None else None
        all_headers = {"Content-Type": "application/json"}
        if token:
            all_headers["Authorization"] = "Bearer " + token
        all_headers.update(headers or {})
        request = Request(self.base + path, data=body, headers=all_headers, method=method)
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            return response.status, json.loads(raw) if "application/json" in response.headers.get("Content-Type", "") else raw

    def login(self, name="student1", password="student123"):
        status, result = self.request("/api/login", "POST", {"username": name, "password": password})
        self.assertEqual(status, 200, result)
        return result["token"]
