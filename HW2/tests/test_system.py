import hashlib
from urllib.parse import quote

from .support import ServerCase


class SystemTests(ServerCase):
    def test_roles_and_authentication_errors(self):
        for username, password in [("admin", "admin123"), ("office", "office123"), ("student1", "student123"), ("teacher1", "teacher123")]:
            token = self.login(username, password)
            status, result = self.request("/api/me", token=token)
            self.assertEqual(status, 200)
            self.assertEqual(result["username"], username)
        self.assertEqual(self.request("/api/login", "POST", {"username": "student1", "password": "wrong"})[0], 401)
        self.assertEqual(self.request("/api/courses")[0], 403)
        self.assertEqual(self.request("/api/courses", token="forged")[0], 403)

    def test_core_flow_and_restart_persistence(self):
        token = self.login()
        status, rows = self.request("/api/courses?q=" + quote("程式設計"), token=token)
        self.assertEqual(status, 200)
        self.assertEqual(rows[0]["code"], "CS101")
        self.assertEqual(self.request("/api/enroll", "POST", {"course_id": 1}, token)[0], 201)
        self.assertEqual(self.request("/api/enroll", "POST", {"course_id": 1}, token)[0], 409)
        status, result = self.request("/api/leave", "POST", {"start_date": "2026-10-05", "end_date": "2026-10-05", "reason": "病假"}, token)
        self.assertEqual(status, 201)
        leave_id = result["id"]
        office = self.login("office", "office123")
        for reviewer in (office, self.login("teacher1", "teacher123"), self.login("admin", "admin123")):
            status, requests = self.request("/api/leave", token=reviewer)
            self.assertEqual(status, 200)
            self.assertTrue(any(row["id"] == leave_id and row["status"] == "pending" for row in requests))
        self.assertEqual(self.request(f"/api/leave/{leave_id}/review", "POST", {"status": "approved"}, office)[0], 200)
        self.stop_server()
        self.db.initialize()
        self.start_server()
        self.assertEqual(self.request("/api/schedule", token=token)[1][0]["code"], "CS101")
        self.assertEqual(self.request("/api/leave", token=token)[1][0]["status"], "approved")
        self.assertEqual(self.request("/api/leave", token=self.login("student2"))[1][0]["reason"], "回診（示範資料）")

    def test_permissions_invalid_data_and_expired_session(self):
        student = self.login()
        teacher = self.login("teacher1", "teacher123")
        self.assertEqual(self.request("/api/users", token=student)[0], 403)
        self.assertEqual(self.request("/api/enroll", "POST", {"course_id": 1}, teacher)[0], 403)
        self.assertEqual(self.request("/api/leave/1/review", "POST", {"status": "approved"}, student)[0], 403)
        self.assertEqual(self.request("/api/leave/999/review", "POST", {"status": "approved"}, teacher)[0], 404)
        self.assertEqual(self.request("/api/enroll", "POST", {"course_id": "1"}, student)[0], 400)
        self.assertEqual(self.request("/api/enroll", "POST", [1], student)[0], 400)
        with self.db.connection(write=True) as conn:
            conn.execute("UPDATE sessions SET expires_at=0 WHERE token_hash=?", (hashlib.sha256(student.encode()).hexdigest(),))
        self.assertEqual(self.request("/api/schedule", token=student)[0], 403)

    def test_admin_management_settings_and_backup(self):
        admin = self.login("admin", "admin123")
        status, user = self.request("/api/users", "POST", {"username": "student3", "password": "student123", "full_name": "測試學生", "role": "student", "active": True}, admin)
        self.assertEqual(status, 201)
        self.assertNotIn("password_hash", user)
        self.assertEqual(self.request("/api/settings", "PUT", {"school_name": "測試學校", "semester": "測試學期", "enrollment_open": False}, admin)[0], 200)
        self.assertEqual(self.request("/api/enroll", "POST", {"course_id": 1}, self.login("student3"))[0], 409)
        self.assertEqual(self.request("/api/backup", "POST", {}, admin)[0], 200)
        self.assertGreater(len(self.request("/api/audit", token=admin)[1]), 0)

    def test_csrf_cookie_and_static_assets(self):
        token = self.login()
        status, _ = self.request("/api/enroll", "POST", {"course_id": 1}, headers={"Cookie": "session=" + token})
        self.assertEqual(status, 403)
        status, _ = self.request("/api/enroll", "POST", {"course_id": 1}, headers={"Cookie": "session=" + token, "X-Requested-With": "SchoolPortal"})
        self.assertEqual(status, 201)
        self.assertEqual(self.request("/api/logout", "POST", {}, token, {"Origin": "https://other.example"})[0], 403)
        self.assertEqual(self.request("/")[0], 200)
        self.assertEqual(self.request("/app.js")[0], 200)
        self.assertEqual(self.request("/../app.py")[0], 404)

    def test_course_management_and_capacity_over_http(self):
        office = self.login("office", "office123")
        teacher_id = self.users["teacher1"]["id"]
        data = {"code": "CS202", "name": "資料結構", "teacher_id": teacher_id, "credits": 3,
                "capacity": 1, "weekday": 2, "start_period": 1, "end_period": 3, "room": "A102"}
        status, course = self.request("/api/courses", "POST", data, office)
        self.assertEqual(status, 201)
        student = self.login()
        student2 = self.login("student2")
        self.assertEqual(self.request("/api/enroll", "POST", {"course_id": course["id"]}, student)[0], 201)
        self.assertEqual(self.request("/api/enroll", "POST", {"course_id": course["id"]}, student2)[0], 409)
        self.assertEqual(self.request(f"/api/courses/{course['id']}", "DELETE", token=office)[0], 409)
        self.assertEqual(self.request(f"/api/enroll/{course['id']}", "DELETE", token=student)[0], 200)
        data["name"] = "資料結構（更新）"
        self.assertEqual(self.request(f"/api/courses/{course['id']}", "PUT", data, office)[0], 200)
        self.assertEqual(self.request(f"/api/courses/{course['id']}", "DELETE", token=office)[0], 200)

    def test_invalid_dates_review_and_student_data_isolation(self):
        student = self.login()
        self.assertEqual(self.request("/api/schedule?student_id=4", token=student)[1], [])
        self.assertEqual(self.request("/api/leave?student_id=4", token=student)[1], [])
        data = {"start_date": "2026-02-30", "end_date": "2026-03-01", "reason": "病假"}
        self.assertEqual(self.request("/api/leave", "POST", data, student)[0], 400)
        office = self.login("office", "office123")
        self.assertEqual(self.request("/api/leave/1/review", "POST", {"status": "unknown"}, office)[0], 400)
        self.assertEqual(self.request("/api/leave/1/review", "POST", {"status": "rejected"}, office)[0], 200)
        self.assertEqual(self.request("/api/leave/1/review", "POST", {"status": "approved"}, office)[0], 409)
