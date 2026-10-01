from .common import APIError, audit, require_role, text


def settings(database):
    with database.connection() as conn:
        return {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}


def save_settings(database, user, data):
    require_role(user, "admin")
    name = text(data, "school_name", 80)
    semester = text(data, "semester", 80)
    opened = data.get("enrollment_open")
    if type(opened) is not bool:
        raise APIError("enrollment_open 必須為布林值")
    with database.connection(write=True) as conn:
        conn.executemany("UPDATE settings SET value=? WHERE key=?", [(name, "school_name"), (semester, "semester"), ("true" if opened else "false", "enrollment_open")])
        audit(conn, user["id"], "save_settings", "settings")
    return settings(database)


def logs(database, user):
    require_role(user, "admin")
    with database.connection() as conn:
        return [dict(r) for r in conn.execute("SELECT a.*,u.username FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 100")]


def backup(database, user):
    require_role(user, "admin")
    path = database.backup()
    with database.connection(write=True) as conn:
        audit(conn, user["id"], "backup", path.name)
    return {"message": "備份完成", "filename": path.name}
