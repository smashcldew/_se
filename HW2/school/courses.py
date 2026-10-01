from .common import APIError, audit, integer, text, require_role

COURSE_SELECT = """SELECT c.*, u.full_name AS teacher_name,
 (SELECT count(*) FROM enrollments e WHERE e.course_id=c.id) AS enrolled_count
 FROM courses c JOIN users u ON u.id=c.teacher_id"""


def list_courses(database, user, keyword=""):
    if len(keyword) > 200:
        raise APIError("搜尋字串過長")
    # Treat wildcard characters as literal search text.
    keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with database.connection() as conn:
        rows = conn.execute(COURSE_SELECT + " WHERE c.code LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\' ORDER BY c.weekday,c.start_period,c.id",
                            (f"%{keyword}%", f"%{keyword}%")).fetchall()
        selected = {r[0] for r in conn.execute("SELECT course_id FROM enrollments WHERE student_id=?", (user["id"],))}
        return [dict(row, enrolled=row["id"] in selected) for row in rows]


def save_course(database, user, data, course_id=None):
    require_role(user, "admin", "administrative")
    code, name, room = text(data, "code", 32), text(data, "name", 100), text(data, "room", 80)
    teacher = integer(data, "teacher_id")
    credits = integer(data, "credits", 0, 10)
    capacity = integer(data, "capacity", 1, 1000)
    day = integer(data, "weekday", 1, 7)
    start, end = integer(data, "start_period", 1, 12), integer(data, "end_period", 1, 12)
    if end < start:
        raise APIError("結束節次不可早於開始節次")
    with database.connection(write=True) as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id=? AND role='teacher' AND active=1", (teacher,)).fetchone():
            raise APIError("請指定有效的教師")
        if course_id is not None:
            old = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
            if not old:
                raise APIError("課程不存在", 404)
            count = conn.execute("SELECT count(*) FROM enrollments WHERE course_id=?", (course_id,)).fetchone()[0]
            if capacity < count:
                raise APIError("容量不可低於目前選課人數", 409)
            if count and any(old[k] != data[k] for k in ("weekday", "start_period", "end_period")):
                raise APIError("已有學生選課，不能直接變更上課時間", 409)
        if conn.execute("SELECT 1 FROM courses WHERE code=? AND id<>?", (code, course_id or 0)).fetchone():
            raise APIError("課程代碼已存在", 409)
        if conn.execute("SELECT 1 FROM courses WHERE id<>? AND weekday=? AND start_period<=? AND end_period>=? AND (teacher_id=? OR room=?)",
                        (course_id or 0, day, end, start, teacher, room)).fetchone():
            raise APIError("教師或教室的上課時間衝突", 409)
        values = (code, name, teacher, credits, capacity, day, start, end, room)
        if course_id is None:
            course_id = conn.execute("INSERT INTO courses(code,name,teacher_id,credits,capacity,weekday,start_period,end_period,room) VALUES(?,?,?,?,?,?,?,?,?)", values).lastrowid
        else:
            conn.execute("UPDATE courses SET code=?,name=?,teacher_id=?,credits=?,capacity=?,weekday=?,start_period=?,end_period=?,room=? WHERE id=?", (*values, course_id))
        audit(conn, user["id"], "save_course", course_id)
        return dict(conn.execute(COURSE_SELECT + " WHERE c.id=?", (course_id,)).fetchone())


def delete_course(database, user, course_id):
    require_role(user, "admin", "administrative")
    with database.connection(write=True) as conn:
        if not conn.execute("SELECT 1 FROM courses WHERE id=?", (course_id,)).fetchone():
            raise APIError("課程不存在", 404)
        if conn.execute("SELECT 1 FROM enrollments WHERE course_id=?", (course_id,)).fetchone():
            raise APIError("已有學生選課，無法刪除課程", 409)
        conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
        audit(conn, user["id"], "delete_course", course_id)
    return {"message": "課程已刪除"}
