from .common import APIError, audit, date_value, integer, now, require_role, text

STATUSES = ("present", "absent", "late", "excused")


def course_access(conn, user, course_id):
    course = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    if not course:
        raise APIError("課程不存在", 404)
    if user["role"] == "teacher" and course["teacher_id"] != user["id"]:
        raise APIError("只能管理自己的授課課程", 403)
    return course


def list_courses(database, user):
    with database.connection() as conn:
        sql = "SELECT c.* FROM courses c"
        args = ()
        if user["role"] == "teacher":
            sql += " WHERE c.teacher_id=?"
            args = (user["id"],)
        elif user["role"] == "student":
            sql += " WHERE EXISTS(SELECT 1 FROM enrollments e WHERE e.course_id=c.id AND e.student_id=?) OR EXISTS(SELECT 1 FROM attendance a WHERE a.course_id=c.id AND a.student_id=?)"
            args = (user["id"], user["id"])
        return [dict(row) for row in conn.execute(sql + " ORDER BY c.code", args)]


def roster(database, user, course_id):
    require_role(user, "teacher")
    with database.connection() as conn:
        course_access(conn, user, course_id)
        return [dict(row) for row in conn.execute(
            "SELECT u.id,u.username,u.full_name FROM enrollments e JOIN users u ON u.id=e.student_id WHERE e.course_id=? AND u.active=1 AND u.role='student' ORDER BY u.username",
            (course_id,))]


def list_records(database, user, query):
    clauses, args = [], []
    if user["role"] == "student":
        clauses.append("a.student_id=?")
        args.append(user["id"])
    elif user["role"] == "teacher":
        clauses.append("c.teacher_id=?")
        args.append(user["id"])
    course_id = query.get("course_id", [""])[0]
    if course_id:
        if not course_id.isascii() or not course_id.isdigit() or not 1 <= int(course_id) <= 1_000_000:
            raise APIError("課程編號不合法")
        clauses.append("a.course_id=?")
        args.append(int(course_id))
    attendance_date = query.get("date", [""])[0]
    if attendance_date:
        clauses.append("a.attendance_date=?")
        args.append(date_value({"date": attendance_date}, "date").isoformat())
    sql = """SELECT a.*,c.code AS course_code,c.name AS course_name,
             s.full_name AS student_name,s.username AS student_username,
             r.full_name AS recorder_name
             FROM attendance a JOIN courses c ON c.id=a.course_id
             JOIN users s ON s.id=a.student_id JOIN users r ON r.id=a.recorded_by"""
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with database.connection() as conn:
        return [dict(row) for row in conn.execute(
            sql + " ORDER BY a.attendance_date DESC,a.period,c.code,s.username", args)]


def save_record(conn, user, data):
    require_role(user, "teacher")
    course_id = integer(data, "course_id")
    student_id = integer(data, "student_id")
    day = date_value(data, "attendance_date").isoformat()
    period = integer(data, "period", 1, 12)
    status = text(data, "status", 16)
    if status not in STATUSES:
        raise APIError("出缺席狀態不合法")
    note = text({"note": data.get("note", "")}, "note", 500, 0)
    course = course_access(conn, user, course_id)
    if not course["start_period"] <= period <= course["end_period"]:
        raise APIError("節次必須在該課程的上課節次範圍內")
    key = (course_id, student_id, day, period)
    previous = conn.execute("SELECT id FROM attendance WHERE course_id=? AND student_id=? AND attendance_date=? AND period=?", key).fetchone()
    # Keep historical records editable after a student withdraws.
    if not previous and not conn.execute(
        "SELECT 1 FROM enrollments e JOIN users u ON u.id=e.student_id WHERE e.course_id=? AND e.student_id=? AND u.role='student' AND u.active=1",
        (course_id, student_id)).fetchone():
        raise APIError("只能為此課程已選課的有效學生登錄出缺席")
    if status == "excused" and not conn.execute(
        "SELECT 1 FROM leave_requests WHERE student_id=? AND status='approved' AND start_date<=? AND end_date>=?",
        (student_id, day, day)).fetchone():
        raise APIError("該日期尚無老師核准的請假申請，請先完成請假審核")
    timestamp = now()
    conn.execute("""INSERT INTO attendance(course_id,student_id,attendance_date,period,status,note,recorded_by,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(course_id,student_id,attendance_date,period) DO UPDATE SET
                    status=excluded.status,note=excluded.note,recorded_by=excluded.recorded_by,updated_at=excluded.updated_at""",
                 (*key, status, note, user["id"], timestamp, timestamp))
    record_id = conn.execute("SELECT id FROM attendance WHERE course_id=? AND student_id=? AND attendance_date=? AND period=?", key).fetchone()[0]
    audit(conn, user["id"], "save_attendance", record_id)
    return {"id": record_id, "message": "出缺席紀錄已儲存"}


def save(database, user, data):
    require_role(user, "teacher")
    with database.connection(write=True) as conn:
        result = save_record(conn, user, data)
        ensure_class(conn, user, data)
        return result


def ensure_class(conn, user, data):
    course_id = integer(data, "course_id")
    day = date_value(data, "attendance_date").isoformat()
    period = integer(data, "period", 1, 12)
    course = course_access(conn, user, course_id)
    if not course["start_period"] <= period <= course["end_period"]:
        raise APIError("節次必須在該課程的上課節次範圍內")
    count = conn.execute("SELECT count(*) FROM enrollments e JOIN users u ON u.id=e.student_id WHERE e.course_id=? AND u.active=1 AND u.role='student'", (course_id,)).fetchone()[0]
    conn.execute("INSERT OR IGNORE INTO attendance_classes(course_id,attendance_date,period,student_count,recorded_by) VALUES(?,?,?,?,?)",
                 (course_id, day, period, count, user["id"]))
    return dict(conn.execute("SELECT * FROM attendance_classes WHERE course_id=? AND attendance_date=? AND period=?", (course_id, day, period)).fetchone())


def open_class(database, user, data):
    require_role(user, "teacher")
    with database.connection(write=True) as conn:
        result = ensure_class(conn, user, data)
        audit(conn, user["id"], "open_attendance_class", result["id"])
        return result


def list_classes(database, user, query):
    # Reuse validated record filters without returning other students' details.
    clauses, args = [], []
    if user["role"] == "teacher":
        clauses.append("c.teacher_id=?")
        args.append(user["id"])
    elif user["role"] == "student":
        clauses.append("(EXISTS(SELECT 1 FROM enrollments e WHERE e.course_id=a.course_id AND e.student_id=?) OR EXISTS(SELECT 1 FROM attendance r WHERE r.course_id=a.course_id AND r.attendance_date=a.attendance_date AND r.period=a.period AND r.student_id=?))")
        args.extend([user["id"], user["id"]])
    value = query.get("course_id", [""])[0]
    if value:
        if not value.isascii() or not value.isdigit() or len(value) > 7 or not 1 <= int(value) <= 1_000_000:
            raise APIError("課程編號不合法")
        clauses.append("a.course_id=?")
        args.append(int(value))
    value = query.get("date", [""])[0]
    if value:
        clauses.append("a.attendance_date=?")
        args.append(date_value({"date": value}, "date").isoformat())
    sql = "SELECT a.*,c.code AS course_code,c.name AS course_name FROM attendance_classes a JOIN courses c ON c.id=a.course_id"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with database.connection() as conn:
        return [dict(row) for row in conn.execute(sql + " ORDER BY a.attendance_date DESC,a.period,c.code", args)]


def save_roll_call(database, user, data):
    require_role(user, "teacher")
    course_id = integer(data, "course_id")
    day = date_value(data, "attendance_date").isoformat()
    period = integer(data, "period", 1, 12)
    class_status = data.get("class_status", "open")
    if class_status not in ("open", "closed"):
        raise APIError("點名狀態只能為點名中或關閉")
    class_note = text({"note": data.get("class_note", "")}, "note", 500, 0)
    entries = data.get("students")
    if not isinstance(entries, list) or not 0 <= len(entries) <= 1000:
        raise APIError("請提供本堂課的學生點名結果")
    student_ids = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise APIError("點名資料格式錯誤")
        student_ids.append(integer(entry, "student_id"))
    if len(set(student_ids)) != len(student_ids):
        raise APIError("點名學生不可重複")
    with database.connection(write=True) as conn:
        course_access(conn, user, course_id)
        enrolled = {row[0] for row in conn.execute(
            "SELECT e.student_id FROM enrollments e JOIN users u ON u.id=e.student_id WHERE e.course_id=? AND u.active=1 AND u.role='student'", (course_id,))}
        if enrolled != set(student_ids):
            raise APIError("選課名單已變動，請重新開啟本堂課點名", 409)
        for entry in entries:
            if entry.get("status") == "":
                # Leaving an existing result blank explicitly resets it to unmarked.
                conn.execute("DELETE FROM attendance WHERE course_id=? AND attendance_date=? AND period=? AND student_id=?",
                             (course_id, day, period, entry["student_id"]))
            else:
                save_record(conn, user, {**entry, "course_id": course_id, "attendance_date": day, "period": period})
        lesson = ensure_class(conn, user, data)
        conn.execute("UPDATE attendance_classes SET status=?,note=?,student_count=?,recorded_by=? WHERE id=?",
                     (class_status, class_note, len(entries), user["id"], lesson["id"]))
        audit(conn, user["id"], "save_attendance_class", lesson["id"])
    return {"message": f"本堂課點名已儲存，共 {len(entries)} 位學生", "count": len(entries)}


def register(router):
    router.add("GET", "/api/attendance/classes", lambda c: list_classes(c.db, c.user, c.query))
    router.add("POST", "/api/attendance/classes", lambda c: open_class(c.db, c.user, c.data), roles=("teacher",))
    router.add("GET", "/api/attendance", lambda c: list_records(c.db, c.user, c.query))
    router.add("GET", "/api/attendance/courses", lambda c: list_courses(c.db, c.user))
    router.add("GET", "/api/attendance/courses/{id}/students", lambda c: roster(c.db, c.user, c.params["id"]), roles=("teacher",))
    router.add("POST", "/api/attendance", lambda c: save(c.db, c.user, c.data), roles=("teacher",))
    router.add("POST", "/api/attendance/roll-call", lambda c: save_roll_call(c.db, c.user, c.data), roles=("teacher",))
