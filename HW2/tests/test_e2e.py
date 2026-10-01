"""Real-browser workflows; require requirements-dev and a Playwright browser."""
import os

from playwright.sync_api import sync_playwright, expect
from .support import ServerCase


class BrowserTests(ServerCase):
    def setUp(self):
        super().setUp()
        self.playwright = sync_playwright().start()
        self.addCleanup(self.playwright.stop)
        channel = os.environ.get("HW2_BROWSER_CHANNEL")
        self.browser = self.playwright.chromium.launch(headless=True, **({"channel": channel} if channel else {}))
        self.addCleanup(self.browser.close)
        self.page = self.browser.new_page()
        self.page.goto(self.base)

    def login_ui(self, username, password):
        form = self.page.locator("#login-form")
        form.get_by_label("帳號", exact=True).fill(username)
        form.get_by_label("密碼", exact=True).fill(password)
        self.page.get_by_role("button", name="登入", exact=True).click()
        expect(self.page.locator("#portal")).to_be_visible()
        expect(self.page.locator("#content")).to_contain_text("程式設計")

    def test_student_enrollment_and_leave_review(self):
        self.login_ui("student1", "student123")
        self.page.get_by_label("課程搜尋").fill("程式設計")
        self.page.get_by_role("button", name="搜尋", exact=True).click()
        expect(self.page.locator("#content")).not_to_contain_text("資料庫系統")
        self.page.get_by_role("row").filter(has_text="程式設計").get_by_role("button", name="選課", exact=True).click()
        expect(self.page.locator("#message")).to_have_text("選課成功")
        self.page.get_by_role("button", name="我的課表", exact=True).click()
        expect(self.page.locator("#content")).to_contain_text("A101")
        expect(self.page.get_by_role("columnheader", name="星期一", exact=True)).to_be_visible()
        for period in (1, 2, 3):
            row = self.page.get_by_role("row").filter(
                has=self.page.get_by_role("cell", name=f"第 {period} 節", exact=True)
            )
            expect(row.get_by_role("cell").nth(1)).to_contain_text("程式設計")
            expect(row.get_by_role("cell").nth(1)).to_contain_text("A101")
        self.page.get_by_role("button", name="請假申請", exact=True).click()
        self.page.get_by_label("開始日期").fill("2026-10-05")
        self.page.get_by_label("結束日期").fill("2026-10-05")
        self.page.get_by_label("請假原因").fill("E2E 學生病假")
        self.page.get_by_role("button", name="送出申請").click()
        expect(self.page.get_by_role("row").filter(has_text="E2E 學生病假")).to_contain_text("待審核")
        self.page.get_by_role("button", name="登出", exact=True).click()
        expect(self.page.locator("#login-view")).to_be_visible()
        self.login_ui("office", "office123")
        self.page.get_by_role("button", name="請假審核", exact=True).click()
        self.page.get_by_role("row").filter(has_text="E2E 學生病假").get_by_role("button", name="核准", exact=True).click()
        expect(self.page.get_by_role("row").filter(has_text="E2E 學生病假")).to_contain_text("已核准")
        self.page.get_by_role("button", name="登出", exact=True).click()
        expect(self.page.locator("#login-view")).to_be_visible()
        self.login_ui("student1", "student123")
        self.page.get_by_role("button", name="請假申請", exact=True).click()
        expect(self.page.get_by_role("row").filter(has_text="E2E 學生病假")).to_contain_text("已核准")

    def test_teacher_timetable_and_rejection(self):
        self.login_ui("teacher1", "teacher123")
        self.page.get_by_role("button", name="授課課表", exact=True).click()
        expect(self.page.locator("#content")).to_contain_text("資料庫系統")
        self.page.get_by_role("button", name="請假審核", exact=True).click()
        self.page.get_by_role("row").filter(has_text="回診（示範資料）").get_by_role("button", name="駁回", exact=True).click()
        expect(self.page.get_by_role("row").filter(has_text="回診（示範資料）")).to_contain_text("已駁回")

    def test_student_cannot_review_and_forged_session(self):
        self.login_ui("student1", "student123")
        expect(self.page.get_by_role("button", name="使用者管理", exact=True)).to_have_count(0)
        response = self.page.request.post(self.base + "/api/leave/1/review", data={"status": "approved"}, headers={"X-Requested-With": "SchoolPortal"})
        self.assertEqual(response.status, 403)
        response = self.page.request.post(self.base + "/api/enroll", data={"course_id": 999}, headers={"X-Requested-With": "SchoolPortal"})
        self.assertEqual(response.status, 404)
        with self.db.connection(write=True) as conn:
            conn.execute("UPDATE sessions SET expires_at=0")
        response = self.page.request.get(self.base + "/api/schedule")
        self.assertEqual(response.status, 403)
        self.page.reload()
        expect(self.page.locator("#login-view")).to_be_visible()
        self.page.context.clear_cookies()
        self.page.context.add_cookies([{"name": "session", "value": "forged", "url": self.base}])
        self.page.reload()
        expect(self.page.locator("#login-view")).to_be_visible()

    def test_admin_creates_user_and_changes_settings(self):
        self.login_ui("admin", "admin123")
        self.page.get_by_role("button", name="使用者管理", exact=True).click()
        self.page.get_by_role("button", name="新增使用者", exact=True).click()
        editor = self.page.locator("#editor")
        editor.get_by_label("帳號", exact=True).fill("e2e_student")
        editor.get_by_label("姓名", exact=True).fill("E2E 學生")
        editor.get_by_label("密碼", exact=True).fill("student123")
        editor.get_by_role("button", name="儲存使用者", exact=True).click()
        expect(self.page.get_by_role("row").filter(has_text="e2e_student")).to_contain_text("學生")
        self.page.get_by_role("button", name="系統設定", exact=True).click()
        self.page.get_by_label("學校名稱", exact=True).fill("E2E 示範學校")
        self.page.get_by_label("開放選課與退選").uncheck()
        self.page.get_by_role("button", name="儲存設定", exact=True).click()
        expect(self.page.locator("#message")).to_have_text("設定已儲存")
        self.page.get_by_role("button", name="登出", exact=True).click()
        expect(self.page.locator("#login-view")).to_be_visible()
        self.login_ui("e2e_student", "student123")
        self.page.get_by_role("button", name="課程查詢", exact=True).click()
        expect(self.page.get_by_role("row").filter(has_text="程式設計").get_by_role("button", name="選課", exact=True)).to_be_disabled()
