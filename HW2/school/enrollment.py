from .common import APIError, audit, integer, now, require_role


def enroll(database, user, data):
    require_role(user, "student")
    course_id = integer(data, "course_id")
    # Lock before capacity check so simultaneous requests cannot overbook.
    with database.connection(write=True) as conn:
        setting = conn.execute("SELECT value FROM settings WHERE key='enrollment_open'").fetchone()
        if not setting or setting[0] != "true":
            raise APIError("目前未開放選課", 409)
        course = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        if not course:
            raise APIError("課程不存在", 404)
        if conn.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?", (user["id"], course_id)).fetchone():
            raise APIError("已選修此課程", 409)
        count = conn.execute("SELECT count(*) FROM enrollments WHERE course_id=?", (course_id,)).fetchone()[0]
        if count >= course["capacity"]:
            raise APIError("課程已額滿", 409)
        conflict = conn.execute("SELECT 1 FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE e.student_id=? AND c.weekday=? AND c.start_period<=? AND c.end_period>=?",
                                (user["id"], course["weekday"], course["end_period"], course["start_period"])).fetchone()
        if conflict:
            raise APIError("與已選課程時間衝突", 409)
        conn.execute("INSERT INTO enrollments(student_id,course_id,created_at) VALUES(?,?,?)", (user["id"], course_id, now()))
        audit(conn, user["id"], "enroll", course_id)
    return {"message": "選課成功"}


def withdraw(database, user, course_id):
    require_role(user, "student")
    with database.connection(write=True) as conn:
        if conn.execute("SELECT value FROM settings WHERE key='enrollment_open'").fetchone()[0] != "true":
            raise APIError("目前未開放選課／退選", 409)
        if not conn.execute("DELETE FROM enrollments WHERE student_id=? AND course_id=?", (user["id"], course_id)).rowcount:
            raise APIError("未選修此課程", 404)
        audit(conn, user["id"], "withdraw", course_id)
    return {"message": "退選成功"}


def schedule(database, user):
    with database.connection() as conn:
        sql = "SELECT c.*,u.full_name AS teacher_name FROM courses c JOIN users u ON u.id=c.teacher_id"
        if user["role"] == "student":
            sql += " JOIN enrollments e ON e.course_id=c.id WHERE e.student_id=?"
            args = (user["id"],)
        elif user["role"] == "teacher":
            sql += " WHERE c.teacher_id=?"
            args = (user["id"],)
        else:
            args = ()
        return [dict(row) for row in conn.execute(sql + " ORDER BY c.weekday,c.start_period,c.id", args)]
