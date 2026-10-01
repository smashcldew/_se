from .common import APIError, audit, date_value, now, text, require_role


def submit(database, user, data):
    require_role(user, "student")
    start, end = date_value(data, "start_date"), date_value(data, "end_date")
    reason = text(data, "reason", 1000)
    if end < start:
        raise APIError("請假結束日期不可早於開始日期")
    with database.connection(write=True) as conn:
        lid = conn.execute("INSERT INTO leave_requests(student_id,start_date,end_date,reason,created_at) VALUES(?,?,?,?,?)",
                           (user["id"], start.isoformat(), end.isoformat(), reason, now())).lastrowid
        audit(conn, user["id"], "submit_leave", lid)
    return {"id": lid, "status": "pending", "message": "請假申請已送出"}


def list_requests(database, user):
    with database.connection() as conn:
        sql = "SELECT l.*,s.full_name AS student_name,r.full_name AS reviewer_name FROM leave_requests l JOIN users s ON s.id=l.student_id LEFT JOIN users r ON r.id=l.reviewed_by"
        args = ()
        if user["role"] == "student":
            sql += " WHERE l.student_id=?"
            args = (user["id"],)
        return [dict(row) for row in conn.execute(sql + " ORDER BY l.id DESC", args)]


def review(database, user, data, leave_id):
    require_role(user, "admin", "administrative", "teacher")
    status = text(data, "status", 16)
    if status not in ("approved", "rejected"):
        raise APIError("審核狀態只能為 approved 或 rejected")
    with database.connection(write=True) as conn:
        row = conn.execute("SELECT status FROM leave_requests WHERE id=?", (leave_id,)).fetchone()
        if not row:
            raise APIError("請假申請不存在", 404)
        if row["status"] != "pending":
            raise APIError("申請已審核，不能重複審核", 409)
        conn.execute("UPDATE leave_requests SET status=?,reviewed_by=?,reviewed_at=? WHERE id=?", (status, user["id"], now(), leave_id))
        audit(conn, user["id"], "review_leave", leave_id)
    return {"message": "審核完成", "status": status}
