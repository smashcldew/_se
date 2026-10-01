"""Extension routes use the same authentication, error and transaction mechanisms.

Example: define def register(router) in grades.py, then call it here.
router.add('GET', '/api/grades', handler, roles=('student', 'teacher'))
handler(context) returns a JSON-serializable result.
"""

ROADMAP = [
    {"key": "grades", "name": "成績管理", "status": "planned"},
    {"key": "fees", "name": "學費管理", "status": "planned"},
    {"key": "notifications", "name": "公告通知", "status": "planned"},
    {"key": "classrooms", "name": "教室管理", "status": "planned"},
    {"key": "attendance", "name": "點名管理", "status": "planned"},
]


def register(router):
    router.add("GET", "/api/modules", lambda context: ROADMAP)
