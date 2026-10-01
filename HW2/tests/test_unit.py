import hashlib
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

from school import auth, courses, enrollment, leave
from school.common import APIError, require_role
from .support import DatabaseCase


class UnitTests(DatabaseCase):
    def assert_error(self, status, fn, *args):
        with self.assertRaises(APIError) as result:
            fn(*args)
        self.assertEqual(result.exception.status, status)

    def test_passwords_are_salted_and_verify(self):
        first = auth.hash_password("test-password")
        second = auth.hash_password("test-password")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("$argon2id$"))
        self.assertTrue(auth.verify_password(first, "test-password"))
        self.assertFalse(auth.verify_password(first, "wrong-password"))

    def test_seed_idempotency_and_constraints(self):
        self.db.initialize()
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM users").fetchone()[0], 5)
            self.assertEqual(conn.execute("SELECT count(*) FROM courses").fetchone()[0], 3)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO enrollments(student_id,course_id,created_at) VALUES(999,1,'now')")

    def test_sessions_expire_and_logout_revokes(self):
        result = auth.login(self.db, {"username": "student1", "password": "student123"})
        self.assertEqual(auth.authenticate(self.db, result["token"])["username"], "student1")
        self.assert_error(403, auth.authenticate, self.db, "forged")
        with self.db.connection(write=True) as conn:
            conn.execute("UPDATE sessions SET expires_at=?", (int(time.time()) - 1,))
            stored = conn.execute("SELECT token_hash FROM sessions").fetchone()[0]
            self.assertEqual(stored, hashlib.sha256(result["token"].encode()).hexdigest())
        self.assert_error(403, auth.authenticate, self.db, result["token"])
        result = auth.login(self.db, {"username": "student1", "password": "student123"})
        auth.logout(self.db, result["token"])
        self.assert_error(403, auth.authenticate, self.db, result["token"])

    def test_role_rules(self):
        require_role(self.users["admin"], "admin")
        self.assert_error(403, require_role, self.users["student1"], "admin", "teacher")

    def test_search_name_and_code(self):
        self.assertEqual(courses.list_courses(self.db, self.users["student1"], "資料庫")[0]["code"], "DB201")
        self.assertEqual(courses.list_courses(self.db, self.users["student1"], "CS101")[0]["name"], "程式設計")
        self.assertEqual(courses.list_courses(self.db, self.users["student1"], "%"), [])

    def test_duplicate_capacity_and_missing_course(self):
        enrollment.enroll(self.db, self.users["student1"], {"course_id": 1})
        self.assert_error(409, enrollment.enroll, self.db, self.users["student1"], {"course_id": 1})
        with self.db.connection(write=True) as conn:
            conn.execute("UPDATE courses SET capacity=1 WHERE id=1")
        self.assert_error(409, enrollment.enroll, self.db, self.users["student2"], {"course_id": 1})
        self.assert_error(404, enrollment.enroll, self.db, self.users["student1"], {"course_id": 999})

    def test_concurrent_enrollment_never_overbooks(self):
        with self.db.connection(write=True) as conn:
            conn.execute("UPDATE courses SET capacity=1 WHERE id=1")
        def select(name):
            try:
                enrollment.enroll(self.db, self.users[name], {"course_id": 1})
                return 201
            except APIError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(select, ["student1", "student2"]))
        self.assertEqual(sorted(outcomes), [201, 409])

    def test_student_time_conflict(self):
        with self.db.connection(write=True) as conn:
            conn.execute("UPDATE courses SET weekday=1,start_period=2,end_period=4 WHERE id=2")
        enrollment.enroll(self.db, self.users["student1"], {"course_id": 1})
        self.assert_error(409, enrollment.enroll, self.db, self.users["student1"], {"course_id": 2})

    def test_leave_dates_and_state_transition(self):
        student = self.users["student1"]
        for data in [
            {"start_date": "2026-02-30", "end_date": "2026-03-01", "reason": "病假"},
            {"start_date": "2026-10-06", "end_date": "2026-10-05", "reason": "病假"},
            {"start_date": "2026-10-05", "end_date": "2026-10-05", "reason": " "},
        ]:
            self.assert_error(400, leave.submit, self.db, student, data)
        result = leave.submit(self.db, student, {"start_date": "2026-10-05", "end_date": "2026-10-05", "reason": "病假"})
        self.assert_error(400, leave.review, self.db, self.users["office"], {"status": "unknown"}, result["id"])
        leave.review(self.db, self.users["office"], {"status": "approved"}, result["id"])
        self.assert_error(409, leave.review, self.db, self.users["teacher1"], {"status": "rejected"}, result["id"])
        self.assertEqual(leave.list_requests(self.db, student)[0]["status"], "approved")

    def test_isolation_and_backup(self):
        self.assertEqual(enrollment.schedule(self.db, self.users["student1"]), [])
        self.assertEqual(leave.list_requests(self.db, self.users["student1"]), [])
        backup = self.db.backup()
        with sqlite3.connect(backup) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM users").fetchone()[0], 5)
