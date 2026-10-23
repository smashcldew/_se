from school import attendance, auth, courses, enrollment, leave
from school.common import APIError
from .support import DatabaseCase, ServerCase


class AttendanceUnitTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        self.teacher = self.users["teacher1"]
        self.data = {"course_id": 2, "student_id": self.users["student2"]["id"],
                     "attendance_date": "2026-10-07", "period": 3, "status": "present", "note": "點名"}

    def assert_error(self, status, fn, *args):
        with self.assertRaises(APIError) as result:
            fn(*args)
        self.assertEqual(result.exception.status, status)

    def test_updates_periods_and_history(self):
        original = attendance.save(self.db, self.teacher, self.data)
        corrected = attendance.save(self.db, self.teacher, {**self.data, "status": "late", "note": "更正"})
        self.assertEqual(original["id"], corrected["id"])
        attendance.save(self.db, self.teacher, {**self.data, "period": 4, "status": "absent"})
        records = attendance.list_records(self.db, self.users["student2"], {})
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["status"], "late")
        self.assertEqual(records[0]["recorded_by"], self.teacher["id"])
        enrollment.withdraw(self.db, self.users["student2"], 2)
        attendance.save(self.db, self.teacher, {**self.data, "status": "present"})
        self.assertEqual(attendance.list_courses(self.db, self.users["student2"])[0]["id"], 2)
        self.assert_error(409, courses.delete_course, self.db, self.users["admin"], 2)
        self.assert_error(409, auth.save_user, self.db, self.users["admin"],
                          {"username": "student2", "full_name": "陳小華", "role": "teacher"},
                          self.users["student2"]["id"])

    def test_permissions_and_student_scope(self):
        for name in ("student1", "office", "admin"):
            self.assert_error(403, attendance.save, self.db, self.users[name], self.data)
            self.assert_error(403, attendance.roster, self.db, self.users[name], 2)
        other = auth.save_user(self.db, self.users["admin"], {
            "username": "teacher2", "password": "teacher123", "full_name": "另一老師", "role": "teacher"})
        self.assert_error(403, attendance.save, self.db, other, self.data)
        self.assert_error(403, attendance.roster, self.db, other, 2)
        attendance.save(self.db, self.teacher, self.data)
        self.assertEqual(attendance.list_records(self.db, other, {}), [])
        self.assertEqual(attendance.list_records(self.db, self.users["student1"], {"student_id": ["4"]}), [])
        self.assertEqual(len(attendance.list_records(self.db, self.users["office"], {})), 1)

    def test_validation_and_approved_leave(self):
        for changes in ({"status": "invalid"}, {"attendance_date": "2026-02-30"},
                        {"period": 1}, {"period": True}, {"student_id": self.users["student1"]["id"]},
                        {"note": "x" * 501}, {"status": "excused"}):
            self.assert_error(400, attendance.save, self.db, self.teacher, {**self.data, **changes})
        self.assert_error(404, attendance.save, self.db, self.teacher, {**self.data, "course_id": 999})
        data = {**self.data, "attendance_date": "2026-10-05", "status": "excused"}
        self.assert_error(400, attendance.save, self.db, self.teacher, data)
        leave.review(self.db, self.teacher, {"status": "approved"}, 1)
        attendance.save(self.db, self.teacher, data)
        self.assertEqual(attendance.list_records(self.db, self.users["student2"], {})[0]["status"], "excused")

    def test_initialize_existing_database_preserves_data(self):
        # Simulate the prior schema, whose seeded marker already exists.
        with self.db.connection(write=True) as conn:
            conn.execute("DROP TABLE attendance")
            conn.execute("UPDATE settings SET value='保留校名' WHERE key='school_name'")
        self.db.initialize()
        attendance.save(self.db, self.teacher, self.data)
        self.db.initialize()
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT value FROM settings WHERE key='school_name'").fetchone()[0], "保留校名")
            self.assertEqual(conn.execute("SELECT count(*) FROM users").fetchone()[0], 5)
            self.assertEqual(conn.execute("SELECT count(*) FROM attendance").fetchone()[0], 1)

    def test_roll_call_atomic_updates_and_roster_validation(self):
        enrollment.enroll(self.db, self.users["student1"], {"course_id": 2})
        first, second = self.users["student1"]["id"], self.users["student2"]["id"]
        data = {"course_id": 2, "attendance_date": "2026-10-07", "period": 3,
                "students": [{"student_id": first, "status": "present"},
                             {"student_id": second, "status": "excused"}]}
        self.assert_error(400, attendance.save_roll_call, self.db, self.teacher, data)
        self.assertEqual(attendance.list_records(self.db, self.teacher, {}), [])
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM audit_logs WHERE action='save_attendance'").fetchone()[0], 0)
        data["students"][1]["status"] = "absent"
        self.assertEqual(attendance.save_roll_call(self.db, self.teacher, data)["count"], 2)
        data["students"][0]["status"] = "late"
        attendance.save_roll_call(self.db, self.teacher, data)
        self.assertEqual(len(attendance.list_records(self.db, self.teacher, {})), 2)
        self.assert_error(409, attendance.save_roll_call, self.db, self.teacher, {**data, "students": []})
        for invalid in ([None], [data["students"][0], data["students"][0]]):
            self.assert_error(400, attendance.save_roll_call, self.db, self.teacher, {**data, "students": invalid})
        enrollment.withdraw(self.db, self.users["student1"], 2)
        self.assert_error(409, attendance.save_roll_call, self.db, self.teacher, data)

    def test_class_summary_lifecycle_and_scope(self):
        lesson = attendance.open_class(self.db, self.teacher, self.data)
        self.assertEqual(lesson["status"], "open")
        self.assertEqual(lesson["student_count"], 1)
        self.assertEqual(attendance.list_records(self.db, self.teacher, {}), [])
        self.assertEqual(attendance.list_classes(self.db, self.users["student1"], {}), [])
        self.assertEqual(len(attendance.list_classes(self.db, self.users["student2"], {})), 1)
        data = {**self.data, "class_status": "closed", "class_note": "缺席 0 人（老師填寫）",
                "students": [{"student_id": self.data["student_id"], "status": ""}]}
        attendance.save_roll_call(self.db, self.teacher, data)
        reopened = attendance.open_class(self.db, self.teacher, self.data)
        self.assertEqual(reopened["id"], lesson["id"])
        self.assertEqual(reopened["status"], "closed")
        self.assertEqual(reopened["note"], data["class_note"])
        for name in ("student2", "office", "admin"):
            self.assert_error(403, attendance.open_class, self.db, self.users[name], self.data)
        self.assert_error(400, attendance.save_roll_call, self.db, self.teacher, {**data, "class_status": "bad"})
        self.assert_error(400, attendance.save_roll_call, self.db, self.teacher, {**data, "class_note": "x" * 501})
        self.assert_error(409, courses.delete_course, self.db, self.users["admin"], 2)

    def test_legacy_class_migration_preserves_manual_notes(self):
        attendance.save(self.db, self.teacher, self.data)
        with self.db.connection(write=True) as conn:
            conn.execute("DROP TABLE attendance_classes")
        self.db.initialize()
        lesson = attendance.list_classes(self.db, self.teacher, {})[0]
        self.assertEqual((lesson["status"], lesson["student_count"]), ("closed", 1))
        with self.db.connection(write=True) as conn:
            conn.execute("UPDATE attendance_classes SET note='自填備註', status='open'")
        self.db.initialize()
        lesson = attendance.list_classes(self.db, self.teacher, {})[0]
        self.assertEqual((lesson["status"], lesson["note"]), ("open", "自填備註"))


class AttendanceSystemTests(ServerCase):
    def test_class_routes_and_role_scope(self):
        data = {"course_id": 2, "attendance_date": "2026-10-07", "period": 3}
        self.assertEqual(self.request("/api/attendance/classes")[0], 403)
        teacher = self.login("teacher1", "teacher123")
        status, lesson = self.request("/api/attendance/classes", "POST", data, teacher)
        self.assertEqual(status, 200)
        self.assertEqual(lesson["status"], "open")
        for name, password, count in (("student1", "student123", 0), ("student2", "student123", 1),
                                       ("office", "office123", 1), ("admin", "admin123", 1)):
            token = self.login(name, password)
            self.assertEqual(self.request("/api/attendance/classes", "POST", data, token)[0], 403)
            rows = self.request("/api/attendance/classes?course_id=2&date=2026-10-07", token=token)[1]
            self.assertEqual(len(rows), count)
        self.assertEqual(self.request("/api/attendance/classes?date=2026-02-30", token=teacher)[0], 400)

    def test_roll_call_route_roles_and_course_scope(self):
        data = {"course_id": 2, "attendance_date": "2026-10-07", "period": 3,
                "students": [{"student_id": self.users["student2"]["id"], "status": "present"}]}
        for username, password in (("student2", "student123"), ("office", "office123"), ("admin", "admin123")):
            token = self.login(username, password)
            self.assertEqual(self.request("/api/attendance/roll-call", "POST", data, token)[0], 403)
        auth.save_user(self.db, self.users["admin"], {"username": "teacher2", "password": "teacher123", "full_name": "其他老師", "role": "teacher"})
        other = self.login("teacher2", "teacher123")
        self.assertEqual(self.request("/api/attendance/roll-call", "POST", data, other)[0], 403)
        token = self.login("teacher1", "teacher123")
        self.assertEqual(self.request("/api/attendance/roll-call", "POST", {**data, "period": 12}, token)[0], 400)
        self.assertEqual(self.request("/api/attendance/roll-call", "POST", data, token)[0], 200)
        self.assertEqual(len(self.request("/api/attendance", token=token)[1]), 1)

    def test_roles_filters_and_persistence(self):
        tokens = {name: self.login(name, password) for name, password in [
            ("teacher1", "teacher123"), ("student1", "student123"), ("student2", "student123"),
            ("office", "office123"), ("admin", "admin123")]}
        teacher = tokens["teacher1"]
        data = {"course_id": 2, "student_id": self.users["student2"]["id"],
                "attendance_date": "2026-10-07", "period": 3, "status": "absent"}
        self.assertEqual(self.request("/api/attendance")[0], 403)
        for name in ("student1", "student2", "office", "admin"):
            self.assertEqual(self.request("/api/attendance", "POST", data, tokens[name])[0], 403)
            self.assertEqual(self.request("/api/attendance/courses/2/students", token=tokens[name])[0], 403)
        self.assertEqual(self.request("/api/attendance/courses/2/students", token=teacher)[1][0]["id"], self.users["student2"]["id"])
        self.assertEqual(self.request("/api/attendance", "POST", data, teacher)[0], 200)
        self.assertEqual(self.request("/api/attendance?student_id=4", token=tokens["student1"])[1], [])
        for name in ("student2", "office", "admin", "teacher1"):
            records = self.request("/api/attendance?course_id=2&date=2026-10-07", token=tokens[name])[1]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["status"], "absent")
        self.assertEqual(self.request("/api/attendance?course_id=1", token=teacher)[1], [])
        self.assertEqual(self.request("/api/attendance?date=2026-10-08", token=teacher)[1], [])
        self.assertEqual(self.request("/api/attendance?course_id=invalid", token=teacher)[0], 400)
        self.assertEqual(self.request("/api/attendance?date=2026-02-30", token=teacher)[0], 400)
        self.request("/api/attendance", "POST", {**data, "status": "present"}, teacher)
        self.stop_server()
        self.db.initialize()
        self.start_server()
        self.assertEqual(self.request("/api/attendance", token=tokens["student2"])[1][0]["status"], "present")
        self.assertEqual(self.request("/attendance.js")[0], 200)
        self.assertFalse(any(m["key"] == "attendance" for m in self.request("/api/modules", token=teacher)[1]))

    def test_teacher_cannot_access_other_course(self):
        other = auth.save_user(self.db, self.users["admin"], {
            "username": "teacher2", "password": "teacher123", "full_name": "另一老師", "role": "teacher"})
        with self.db.connection(write=True) as conn:
            conn.execute("UPDATE courses SET teacher_id=? WHERE id=2", (other["id"],))
        data = {"course_id": 2, "student_id": self.users["student2"]["id"],
                "attendance_date": "2026-10-07", "period": 3, "status": "present"}
        owner = self.login("teacher2", "teacher123")
        self.assertEqual(self.request("/api/attendance", "POST", data, owner)[0], 200)
        other_token = self.login("teacher1", "teacher123")
        self.assertEqual(self.request("/api/attendance", "POST", data, other_token)[0], 403)
        self.assertEqual(self.request("/api/attendance/courses/2/students", token=other_token)[0], 403)
        self.assertEqual(self.request("/api/attendance?course_id=2", token=other_token)[1], [])
        self.assertNotIn(2, [c["id"] for c in self.request("/api/attendance/courses", token=other_token)[1]])
