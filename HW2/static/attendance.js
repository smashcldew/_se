"use strict";

// Self-contained attendance UI; the portal supplies its shared API/dialog helpers.
window.AttendanceModule = (() => {
  const statuses = {present: "出席", absent: "缺席", late: "遲到", excused: "請假"};
  let context, filter, courses = [], records = [], session = null;
  function reset() { filter = {course_id: "", date: ""}; courses = []; records = []; session = null; }
  reset();

  async function render() {
    const {api, escape, table, user} = context;
    [courses, records] = await Promise.all([
      api("/api/attendance/courses"), api("/api/attendance/classes?" + new URLSearchParams(filter)),
    ]);
    const teacher = user().role === "teacher";
    const counts = `點名中 ${records.filter(r => r.status === "open").length} 堂 · 關閉 ${records.filter(r => r.status === "closed").length} 堂`;
    return `<p class="muted">${teacher ? "可從課程清單按「開啟點名」，或在此選擇課程並查詢，再開啟整堂課點名。" : user().role === "student" ? "查看自己的出缺席紀錄；尚未登錄的節次不會視為缺席。" : "查閱各課程出缺席紀錄，登錄與更正由授課老師負責。"}</p>
      <form id="attendance-filter" class="attendance-filter"><label>課程<select name="course_id"><option value="">全部課程</option>${courses.map(c => `<option value="${c.id}" ${String(c.id) === filter.course_id ? "selected" : ""}>${escape(c.code)} · ${escape(c.name)}</option>`).join("")}</select></label><label>日期<input type="date" name="date" value="${escape(filter.date)}"></label><button type="submit">查詢</button><button type="button" class="secondary" data-action="clear-attendance">清除篩選</button></form>
      <div class="toolbar"><div aria-label="出缺席統計">${counts}</div>${teacher ? `<button data-action="new-attendance" ${filter.course_id ? "" : "disabled"}>開啟點名</button>` : ""}</div>
      ${table(["日期節次", "課程", "學生人數", "狀態", "備註／缺席人數（老師填寫）", "修改"], records.map(r => `<tr><td>${escape(r.attendance_date)}<small>第 ${r.period} 節</small></td><td>${escape(r.course_name)}<small>${escape(r.course_code)}</small></td><td>${r.student_count} 人</td><td><span class="badge ${r.status === "open" ? "pending" : "approved"}">${r.status === "open" ? "點名中" : "關閉"}</span></td><td>${escape(r.note) || "—"}</td><td><button class="secondary" data-action="${teacher ? "edit-attendance" : "view-attendance"}" data-id="${r.id}">${teacher ? "修改" : "查看"}</button></td></tr>`))}`;
  }

  async function edit(id) {
    const record = records.find(r => r.id === id);
    if (!record) throw new Error("請重新查詢該堂課。");
    await startClass({course_id: record.course_id, attendance_date: record.attendance_date, period: record.period});
  }

  async function viewDetails(id) {
    const {api, escape, table, openEditor} = context;
    const record = records.find(r => r.id === id);
    if (!record) throw new Error("請重新查詢該堂課。");
    const rows = await api("/api/attendance?" + new URLSearchParams({course_id: record.course_id, date: record.attendance_date}));
    openEditor("出缺席明細", `<p>${escape(record.course_name)} · ${escape(record.attendance_date)} · 第 ${record.period} 節</p>${table(["學生", "出缺席", "個人備註"], rows.filter(r => r.period === record.period).map(r => `<tr><td>${escape(r.student_name)}</td><td>${statuses[r.status]}</td><td>${escape(r.note) || "—"}</td></tr>`))}`, "attendance-readonly");
  }
  async function save(data) {
    for (const key of ["course_id", "student_id", "period"]) data[key] = Number(data[key]);
    return context.api("/api/attendance", "POST", data);
  }

  async function openClass(courseId) {
    const {api, escape, input, openEditor} = context;
    courses = await api("/api/attendance/courses");
    const course = courses.find(c => c.id === (courseId || Number(filter.course_id)));
    if (!course) throw new Error("請先選擇自己的授課課程。");
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
    const periods = Array.from({length: course.end_period-course.start_period+1}, (_, i) => course.start_period+i);
    openEditor("開啟點名", `<p><strong>${escape(course.code)} · ${escape(course.name)}</strong></p><input type="hidden" name="course_id" value="${course.id}"><div class="grid-2">${input("attendance_date", "點名日期", filter.date || today, "date", "required")}<label>節次<select name="period">${periods.map(p => `<option value="${p}">第 ${p} 節</option>`).join("")}</select></label></div><p class="muted">開啟後顯示本課程全班名單；已有紀錄會自動帶入。</p><button type="submit">開始點名</button>`, "attendance-setup");
  }

  async function startClass(data) {
    const {api, escape, openEditor} = context;
    const course = courses.find(c => c.id === Number(data.course_id));
    if (!course) throw new Error("課程資料已失效，請重新開啟。");
    const [students, existing] = await Promise.all([
      api(`/api/attendance/courses/${course.id}/students`),
      api("/api/attendance?" + new URLSearchParams({course_id: course.id, date: data.attendance_date})),
    ]);
    const lesson = await api("/api/attendance/classes", "POST", {course_id: course.id, attendance_date: data.attendance_date, period: Number(data.period)});
    await context.refreshClasses();
    session = {course_id: course.id, attendance_date: data.attendance_date, period: Number(data.period), students};
    openEditor("課堂點名", `<p><strong>${escape(course.code)} · ${escape(course.name)}</strong><br>${escape(session.attendance_date)} · 第 ${session.period} 節 · 共 ${students.length} 位學生</p><label>點名狀態<select name="class_status"><option value="open" ${lesson.status === "open" ? "selected" : ""}>點名中</option><option value="closed" ${lesson.status === "closed" ? "selected" : ""}>關閉</option></select></label><label>備註／缺席人數（老師填寫）<textarea name="class_note" maxlength="500" placeholder="例如：缺席 2 人，已通知補課">${escape(lesson.note)}</textarea></label><p class="muted">下方可編輯學生明細；未填寫仍為未點名，不視為缺席。「請假」須已有老師核准的申請。</p><div class="roll-call-list">${students.map(s => {
      const previous = existing.find(r => r.student_id === s.id && r.period === session.period);
      return `<div class="roll-call-row" data-student-id="${s.id}"><div><strong>${escape(s.full_name)}</strong><small>${escape(s.username)}</small></div><label>出缺席狀態<select name="status_${s.id}"><option value="">未點名</option>${Object.entries(statuses).map(([key, label]) => `<option value="${key}" ${previous?.status === key ? "selected" : ""}>${label}</option>`).join("")}</select></label><label>備註<input name="note_${s.id}" maxlength="500" value="${escape(previous?.note || "")}" placeholder="選填"></label></div>`;
    }).join("")}</div><button type="submit">儲存本堂點名</button>`, "attendance-roll-call");
  }

  async function saveClass(data) {
    if (!session) throw new Error("請重新開啟點名。");
    const result = await context.api("/api/attendance/roll-call", "POST", {
      course_id: session.course_id, attendance_date: session.attendance_date, period: session.period,
      class_status: data.class_status, class_note: data.class_note,
      students: session.students.map(s => ({student_id: s.id, status: data[`status_${s.id}`], note: data[`note_${s.id}`]})),
    });
    filter = {course_id: String(session.course_id), date: session.attendance_date};
    return result;
  }

  return {configure: helpers => { context = helpers; }, reset, render, edit, viewDetails, save, openClass, startClass, saveClass,
    setFilter: data => { filter = {course_id: data.course_id, date: data.date}; }};
})();
