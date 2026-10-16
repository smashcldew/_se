"use strict";
const $ = (selector) => document.querySelector(selector);
const roles = {admin: "管理員", administrative: "行政", student: "學生", teacher: "老師"};
const statuses = {pending: "待審核", approved: "已核准", rejected: "已駁回"};
const days = ["", "一", "二", "三", "四", "五", "六", "日"];
const state = {user: null, settings: {}, view: "courses", courses: [], users: [], keyword: "", generation: 0};
const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const period = (c) => `星期${days[c.weekday]} · 第 ${c.start_period}–${c.end_period} 節`;
const manager = () => ["admin", "administrative"].includes(state.user.role);
const canViewSchedule = () => ["student", "teacher", "admin"].includes(state.user.role);
const connectionMessage = "無法連接校務登入服務。請啟動 HW2/start.cmd，並從 http://127.0.0.1:5500 登入。";

function connectionError() {
  $("#connection-help").hidden = false;
  return new Error(connectionMessage);
}

async function api(path, method = "GET", body) {
  if (location.protocol === "file:") throw connectionError();
  let response;
  try {
    response = await fetch(path, {method, credentials: "same-origin", headers: {"Content-Type": "application/json", "X-Requested-With": "SchoolPortal"}, body: body === undefined ? undefined : JSON.stringify(body)});
  } catch {
    throw connectionError();
  }
  if (!response.headers.get("Content-Type")?.includes("application/json")) throw connectionError();
  let result;
  try { result = await response.json(); }
  catch { throw connectionError(); }
  $("#connection-help").hidden = true;
  if (!response.ok) {
    if (response.status === 403 && /登入/.test(result.error)) showLogin();
    throw new Error(result.error || "操作失敗");
  }
  return result;
}

function notify(text, error = false) {
  const message = $("#message");
  message.textContent = text;
  message.className = error ? "error" : "";
  message.hidden = false;
}

function showLogin() {
  state.generation++;
  state.user = null;
  $("#portal").hidden = true;
  $("#login-view").hidden = false;
  setPasswordVisible(false);
  if ($("#editor").open) $("#editor").close();
}

async function showPortal(user) {
  state.user = user;
  AttendanceModule.reset();
  state.settings = await api("/api/settings");
  $("#login-view").hidden = true;
  $("#portal").hidden = false;
  $("#identity").textContent = `${user.full_name} · ${roles[user.role]}`;
  updateHeading();
  state.groups = [
    {title: "教務與學習", note: "查詢課程、安排每週學習", icon: "01", items: [["courses", "課程查詢", "瀏覽課程與選退課"], ["schedule", user.role === "student" ? "我的課表" : user.role === "teacher" ? "授課課表" : "全校課表", "查看每週課程與教室"]]},
    {title: "校園服務", note: "日常申請與檔案作業", icon: "02", items: [["leave", user.role === "student" ? "請假申請" : user.role === "teacher" ? "請假審核" : "請假紀錄", "學生申請、老師審核、行政查閱紀錄"], ["upload", "上傳檔案", "選擇檔案與確認資訊"]]},
  ];
  state.groups[0].items.push(["attendance", "出缺席", user.role === "student" ? "查看自己的上課紀錄" : user.role === "teacher" ? "點名模組：登錄與更正" : "查閱全校出缺席紀錄"]);
  if (!canViewSchedule()) {
    state.groups[0].items = state.groups[0].items.filter(([id]) => id !== "schedule");
    state.groups[0].note = "查詢與維護課程資料";
  }
  if (user.role === "admin") state.groups.push({title: "系統管理", note: "帳號、設定與操作追蹤", icon: "03", items: [["users", "使用者管理", "維護帳號與角色權限"], ["settings", "系統設定", "校務設定與資料備份"], ["audit", "操作紀錄", "檢視最近的系統操作"]]});
  state.groups.push({title: "功能擴充", note: "探索校務服務的下一步", icon: "04", items: [["modules", "功能擴充", "查看後續模組規畫"]]});
  $("#navigation").innerHTML = '<button data-view="home">校務總覽</button>' + state.groups.map(g => `<details class="nav-group" open><summary>${g.title}</summary>${g.items.filter(i => i[0] !== "upload").map(([id, title]) => `<button data-view="${id}">${title}</button>`).join("")}</details>`).join("");
  await navigate("home");
}

function updateHeading() {
  $("#semester").textContent = state.settings.semester;
  $(".brand").innerHTML = `${escape(state.settings.school_name)} <small>Campus Portal</small>`;
}

function table(headers, rows) {
  return `<div class="card table-wrap"><table><thead><tr>${headers.map(h => `<th>${escape(h)}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.join("") : `<tr><td colspan="${headers.length}" class="empty">目前沒有資料</td></tr>`}</tbody></table></div>`;
}

async function navigate(view) {
  state.view = view;
  const generation = ++state.generation;
  $("#message").hidden = true;
  document.querySelectorAll("nav button").forEach(button => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    if (active) { button.setAttribute("aria-current", "page"); const group = button.closest("details"); if (group) group.open = true; }
    else button.removeAttribute("aria-current");
  });
  $("#page-title").textContent = document.querySelector(`nav button[data-view="${view}"]`)?.textContent || "校務系統";
  $("#content").innerHTML = '<div class="empty">載入中…</div>';
  try {
    let html;
    if (view === "home") html = await homeView();
    else if (view === "courses") html = await courseView();
    else if (view === "schedule") html = await scheduleView();
    else if (view === "leave") html = await leaveView();
    else if (view === "attendance") html = await AttendanceModule.render();
    else if (view === "users") html = await userView();
    else if (view === "settings") html = settingsView();
    else if (view === "audit") html = await auditView();
    else if (view === "modules") html = await moduleView();
    if (generation === state.generation) $("#content").innerHTML = html;
  } catch (error) {
    if (generation === state.generation) {
      $("#content").innerHTML = '<div class="empty">資料載入失敗，請重新選擇頁面。</div>';
      notify(error.message, true);
    }
  }
}

async function homeView() {
  const [schedule, leaves] = await Promise.all([canViewSchedule() ? api("/api/schedule") : Promise.resolve(null), api("/api/leave")]);
  const pending = leaves.filter(l => l.status === "pending").length;
  const overviewLabel = schedule === null ? "請假紀錄" : state.user.role === "student" ? "已選課程" : "課表課程";
  const overviewCount = schedule === null ? leaves.length : schedule.length;
  return `<section class="welcome"><div><span class="eyebrow">YOUR CAMPUS, CONNECTED</span><h2>${escape(state.user.full_name)}，歡迎回來。</h2><p>展開需要的功能，開始今天的校園日常。</p></div><span class="welcome-mark" aria-hidden="true">學</span></section>
    <div class="stats"><div class="stat"><span class="muted">${overviewLabel}</span><strong>${overviewCount}<small> ${schedule === null ? "筆" : "門"}</small></strong></div><div class="stat"><span class="muted">待審核請假</span><strong>${pending}<small> 筆</small></strong></div><div class="stat"><span class="muted">選課狀態</span><strong class="stat-text">${state.settings.enrollment_open === "true" ? "開放中" : "已關閉"}</strong></div></div>
    <div class="section-heading"><div><h2>我的校務功能</h2><p class="muted">依需求展開，各項作業集中管理。</p></div><button class="secondary" data-action="toggle-groups">全部展開</button></div>
    <div class="feature-groups">${state.groups.map((g, index) => `<details class="feature-group" ${index === 0 ? "open" : ""}><summary><span class="feature-number">${g.icon}</span><span><strong>${g.title}</strong><small>${g.note}</small></span><span class="group-count">${g.items.length} 項功能</span></summary><div class="feature-items">${g.items.map(([id, title, description]) => `<button class="feature-item" ${id === "upload" ? 'data-action="upload"' : `data-view="${id}"`}><span><strong>${title}</strong><small>${description}</small></span><span aria-hidden="true">↗</span></button>`).join("")}</div></details>`).join("")}</div>`;
}

function editLeave() {
  const now = new Date();
  const date = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
  openEditor("新增請假申請", `<p class="muted">填寫日期與原因，送出後可在請假紀錄查看進度。</p><div class="grid-2">${input("start_date", "開始日期", date, "date", "required")}${input("end_date", "結束日期", date, "date", "required")}</div><label>請假原因<textarea name="reason" required maxlength="1000" placeholder="請說明請假原因"></textarea></label><button type="submit">送出申請</button>`, "leave");
}

function editSettings() {
  openEditor("校務設定", `${input("school_name", "學校名稱", state.settings.school_name, "text", 'required maxlength="80"')}${input("semester", "學期", state.settings.semester, "text", 'required maxlength="80"')}<label><input type="checkbox" name="enrollment_open" ${state.settings.enrollment_open === "true" ? "checked" : ""}>開放選課與退選</label><button type="submit">儲存設定</button>`, "settings");
}

function uploadFile() {
  openEditor("上傳檔案", '<p class="muted">介面預覽：目前尚未連接檔案儲存服務，檔案不會傳送或保存。</p><label class="file-zone">選擇檔案<input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" required><small>PDF、PNG、JPG、TXT，單一檔案上限 10 MB。</small></label><div id="file-preview" class="file-preview" role="status">尚未選擇檔案</div><button type="submit" disabled>確認檔案（預覽）</button>', "upload");
}

async function courseView() {
  const allCourses = await api(`/api/courses?q=${encodeURIComponent(state.keyword)}`);
  const courses = state.user.role === "teacher" ? allCourses.filter(c => c.teacher_id === state.user.id) : allCourses;
  state.courses = courses;
  const rows = courses.map(c => `<tr><td><strong>${escape(c.name)}</strong><small>${escape(c.code)} · ${c.credits} 學分</small></td><td>${escape(c.teacher_name)}</td><td>${period(c)}<small>${escape(c.room)}</small></td><td>${c.enrolled_count} / ${c.capacity}</td><td>${state.user.role === "student" ? `<button data-action="${c.enrolled ? "withdraw" : "enroll"}" data-id="${c.id}" ${state.settings.enrollment_open !== "true" || (!c.enrolled && c.enrolled_count >= c.capacity) ? "disabled" : ""} class="${c.enrolled ? "secondary" : ""}">${c.enrolled ? "退選" : c.enrolled_count >= c.capacity ? "已額滿" : "選課"}</button>` : manager() ? `<button class="secondary" data-action="edit-course" data-id="${c.id}">編輯</button><button class="danger" data-action="delete-course" data-id="${c.id}">刪除</button>` : `<button data-action="open-roll-call" data-id="${c.id}">開啟點名</button>`}</td></tr>`);
  return `<div class="toolbar"><form id="search-form" class="search"><input aria-label="課程搜尋" name="q" placeholder="搜尋課程名稱或代碼" maxlength="200" value="${escape(state.keyword)}"><button>搜尋</button></form>${manager() ? '<button data-action="new-course">新增課程</button>' : `<span class="badge">${state.settings.enrollment_open === "true" ? "選課開放中" : "選課已關閉"}</span>`}</div>${table(["課程", "授課老師", "上課時間 / 教室", "選課人數", "操作"], rows)}`;
}

async function scheduleView() {
  const courses = await api("/api/schedule");
  const rows = [];
  for (let p = 1; p <= 12; p++) {
    let row = `<tr><td>第 ${p} 節</td>`;
    for (let day = 1; day <= 7; day++) {
      row += `<td>${courses.filter(c => c.weekday === day && c.start_period <= p && c.end_period >= p).map(c => `<div class="lesson"><strong>${escape(c.name)}</strong><br>${escape(c.room)} · ${escape(c.teacher_name)}</div>`).join("")}</td>`;
    }
    rows.push(row + "</tr>");
  }
  return `<div class="stats"><div class="stat"><span class="muted">課程數</span><strong>${courses.length}</strong></div><div class="stat"><span class="muted">總學分</span><strong>${courses.reduce((sum, c) => sum + c.credits, 0)}</strong></div><div class="stat"><span class="muted">學期</span><strong>${escape(state.settings.semester.split(" ")[0])}</strong></div></div><div class="schedule">${table(["節次", ...days.slice(1).map(day => `星期${day}`)], rows)}</div>`;
}

async function leaveView() {
  const items = await api("/api/leave");
  const student = state.user.role === "student";
  const teacher = state.user.role === "teacher";
  const rows = items.map(l => `<tr><td>#${l.id}<small>${escape(l.student_name)}</small></td><td>${escape(l.start_date)}<br>至 ${escape(l.end_date)}</td><td>${escape(l.reason)}</td><td><span class="badge ${l.status}">${statuses[l.status]}</span><small>${escape(l.reviewer_name || "")}</small></td><td>${teacher && l.status === "pending" ? `<button data-action="approved" data-id="${l.id}">核准</button><button class="danger" data-action="rejected" data-id="${l.id}">駁回</button>` : "—"}</td></tr>`);
  const form = `<div class="toolbar"><p class="muted">${student ? "提出請假申請後，由老師核准或駁回。" : teacher ? `待審核申請：${items.filter(l => l.status === "pending").length} 筆` : "請假申請與老師審核結果由系統自動留存，此頁僅供查閱紀錄。"}</p>${student ? '<button data-action="new-leave">新增請假申請</button>' : ""}</div>`;
  return form + table(["編號 / 學生", "請假日期", "原因", "狀態 / 審核人", "操作"], rows);
}

async function userView() {
  const users = await api("/api/users");
  state.users = users;
  return `<div class="toolbar"><p class="muted">管理校務帳號與角色權限</p><button data-action="new-user">新增使用者</button></div>${table(["姓名", "帳號", "角色", "狀態", "操作"], users.map(u => `<tr><td>${escape(u.full_name)}</td><td>${escape(u.username)}</td><td>${roles[u.role]}</td><td><span class="badge ${u.active ? "approved" : "rejected"}">${u.active ? "啟用" : "停用"}</span></td><td><button class="secondary" data-action="edit-user" data-id="${u.id}">編輯</button></td></tr>`))}`;
}

function settingsView() {
  return `<div class="module-grid"><div class="card card-body"><h2>校務設定</h2><p>${escape(state.settings.school_name)}</p><p class="muted">${escape(state.settings.semester)} · 選課${state.settings.enrollment_open === "true" ? "開放中" : "已關閉"}</p><button data-action="edit-settings">編輯設定</button></div><div class="card card-body"><h2>資料庫備份</h2><p class="muted">建立目前資料庫的完整副本，保存在伺服器的資料目錄。</p><button data-action="backup-dialog">建立備份</button></div></div>`;
}

async function auditView() {
  const rows = await api("/api/audit");
  return '<p class="muted">顯示最近 100 筆操作紀錄。</p>' + table(["時間", "帳號", "操作", "對象"], rows.map(r => `<tr><td>${escape(new Date(r.created_at).toLocaleString("zh-TW"))}</td><td>${escape(r.username)}</td><td>${escape(r.action)}</td><td>${escape(r.target)}</td></tr>`));
}

async function moduleView() {
  const modules = await api("/api/modules");
  return `<p class="muted">以下為後續擴充方向，目前尚未提供操作功能。</p><div class="module-grid">${modules.map(m => `<div class="card card-body"><h2>${escape(m.name)}</h2><span class="badge">規畫中</span></div>`).join("")}</div>`;
}

function input(name, title, value = "", type = "text", attributes = "") {
  return `<label>${title}<input name="${name}" type="${type}" value="${escape(value)}" ${attributes}></label>`;
}

async function editCourse(id) {
  const teachers = await api("/api/teachers");
  if (!teachers.length) throw new Error("請先由管理員建立有效的教師帳號");
  const course = state.courses.find(c => c.id === id) || {credits: 3, capacity: 30, weekday: 1, start_period: 1, end_period: 2, teacher_id: teachers[0].id};
  const html = `<div class="grid-2">${input("code", "課程代碼", course.code, "text", 'required maxlength="32"')}${input("name", "課程名稱", course.name, "text", 'required maxlength="100"')}</div><label>授課老師<select name="teacher_id">${teachers.map(t => `<option value="${t.id}" ${t.id === course.teacher_id ? "selected" : ""}>${escape(t.full_name)}</option>`).join("")}</select></label><div class="grid-2">${input("credits", "學分", course.credits, "number", 'required min="0" max="10"')}${input("capacity", "人數上限", course.capacity, "number", 'required min="1" max="1000"')}</div><label>星期<select name="weekday">${days.slice(1).map((d, i) => `<option value="${i+1}" ${i+1 === course.weekday ? "selected" : ""}>星期${d}</option>`).join("")}</select></label><div class="grid-2">${input("start_period", "開始節次", course.start_period, "number", 'required min="1" max="12"')}${input("end_period", "結束節次", course.end_period, "number", 'required min="1" max="12"')}</div>${input("room", "教室", course.room, "text", 'required maxlength="80"')}<button>儲存課程</button>`;
  openEditor(id ? "編輯課程" : "新增課程", html, "course", id);
}

function editUser(id) {
  const user = state.users.find(u => u.id === id) || {role: "student", active: true};
  const html = `${input("username", "帳號", user.username, "text", 'required maxlength="64" pattern="[A-Za-z0-9_.\\-]+"')}${input("full_name", "姓名", user.full_name, "text", 'required maxlength="80"')}<label>角色<select name="role">${Object.entries(roles).map(([role, title]) => `<option value="${role}" ${role === user.role ? "selected" : ""}>${title}</option>`).join("")}</select></label>${input("password", id ? "重設密碼（留空則保留原密碼）" : "密碼", "", "password", `${id ? "" : "required"} minlength="8" maxlength="128" autocomplete="new-password"`)}<label><input type="checkbox" name="active" ${user.active ? "checked" : ""}>啟用帳號</label><button>儲存使用者</button>`;
  openEditor(id ? "編輯使用者" : "新增使用者", html, "user", id);
}

function openEditor(title, html, kind, id) {
  $("#editor").classList.toggle("roll-call-dialog", kind === "attendance-roll-call");
  $("#editor-title").textContent = title;
  $("#editor-error").textContent = "";
  const form = $("#editor-form");
  form.innerHTML = html;
  form.dataset.kind = kind;
  form.dataset.id = id || "";
  $("#editor").showModal();
  form.querySelector('input:not([type="hidden"]):not([readonly]), select, textarea, button')?.focus();
}

$("#login-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.target.querySelector('button[type="submit"]');
  button.disabled = true;
  $("#login-error").textContent = "";
  try {
    const result = await api("/api/login", "POST", Object.fromEntries(new FormData(event.target)));
    event.target.reset();
    setPasswordVisible(false);
    await showPortal(result.user);
  } catch (error) { $("#login-error").textContent = error.message; }
  finally { button.disabled = false; }
});

$("#logout").addEventListener("click", async () => {
  try { await api("/api/logout", "POST", {}); showLogin(); }
  catch (error) { notify(error.message, true); }
});
$("#close-editor").addEventListener("click", () => $("#editor").close());
$("#navigation").addEventListener("click", event => {
  const button = event.target.closest("button[data-view]");
  if (button) navigate(button.dataset.view);
});

$("#content").addEventListener("click", async event => {
  const link = event.target.closest("button[data-view]");
  if (link) return navigate(link.dataset.view);
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const action = button.dataset.action, id = Number(button.dataset.id);
  button.disabled = true;
  try {
    if (action === "open-roll-call" || action === "new-attendance") return await AttendanceModule.openClass(id || undefined);
    if (action === "edit-attendance") return await AttendanceModule.edit(id);
    if (action === "view-attendance") return await AttendanceModule.viewDetails(id);
    if (action === "clear-attendance") {
      AttendanceModule.reset();
      return await navigate("attendance");
    }
    if (action === "toggle-groups") {
      const groups = [...document.querySelectorAll(".feature-group")];
      const open = groups.some(g => !g.open);
      groups.forEach(g => g.open = open);
      return;
    }
    if (action === "new-leave") return editLeave();
    if (action === "edit-settings") return editSettings();
    if (action === "upload") return uploadFile();
    if (action === "backup-dialog") return openEditor("建立資料庫備份", '<p>將建立目前資料庫的完整副本，保存於伺服器資料目錄。</p><button type="submit">確認建立備份</button>', "backup");
    if (action === "new-course" || action === "edit-course") return await editCourse(id || undefined);
    if (action === "new-user" || action === "edit-user") return editUser(id || undefined);
    let result;
    if (action === "enroll") result = await api("/api/enroll", "POST", {course_id: id});
    if (action === "withdraw") result = await api(`/api/enroll/${id}`, "DELETE");
    if (action === "approved" || action === "rejected") result = await api(`/api/leave/${id}/review`, "POST", {status: action});
    if (action === "delete-course") {
      return openEditor("刪除課程", '<p>確定刪除此課程？已有學生選課的課程無法刪除。</p><button type="submit" class="danger">確認刪除</button>', "delete-course", id);
    }
    if (action === "backup") result = await api("/api/backup", "POST", {});
    await navigate(state.view);
    notify(result.filename ? `${result.message}：${result.filename}` : result.message);
  } catch (error) { notify(error.message, true); }
  finally { button.disabled = false; }
});

$("#content").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.target;
  const data = Object.fromEntries(new FormData(form));
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    if (form.id === "search-form") { state.keyword = data.q; return await navigate("courses"); }
    if (form.id === "attendance-filter") {
      AttendanceModule.setFilter(data);
      return await navigate("attendance");
    }
    let result;
    if (form.id === "leave-form") result = await api("/api/leave", "POST", data);
    if (form.id === "settings-form") {
      data.enrollment_open = form.elements.enrollment_open.checked;
      state.settings = await api("/api/settings", "PUT", data);
      updateHeading();
      result = {message: "設定已儲存"};
    }
    await navigate(state.view);
    notify(result.message);
  } catch (error) { notify(error.message, true); }
  finally { button.disabled = false; }
});

$("#editor-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.target, id = form.dataset.id;
  const kind = form.dataset.kind;
  const data = Object.fromEntries(new FormData(form));
  const course = kind === "course";
  if (course) for (const key of ["teacher_id", "credits", "capacity", "weekday", "start_period", "end_period"]) data[key] = Number(data[key]);
  else if (kind === "user") {
    data.active = form.elements.active.checked;
    if (id && !data.password) delete data.password;
  }
  const button = form.querySelector("button");
  button.disabled = true;
  $("#editor-error").textContent = "";
  try {
    let message = "儲存成功";
    if (kind === "upload") {
      const file = form.elements.file.files[0];
      const error = validateFile(file);
      if (error) throw new Error(error);
      $("#file-preview").textContent = `已確認：${file.name}。此為介面預覽，檔案尚未上傳。`;
      return;
    } else if (kind === "attendance-setup") {
      return await AttendanceModule.startClass(data);
    } else if (kind === "attendance-roll-call") {
      message = (await AttendanceModule.saveClass(data)).message;
    } else if (kind === "attendance") {
      message = (await AttendanceModule.save(data)).message;
    } else if (kind === "leave") {
      message = (await api("/api/leave", "POST", data)).message;
    } else if (kind === "settings") {
      data.enrollment_open = form.elements.enrollment_open.checked;
      state.settings = await api("/api/settings", "PUT", data);
      updateHeading();
      message = "設定已儲存";
    } else if (kind === "backup") {
      const result = await api("/api/backup", "POST", {});
      message = `${result.message}：${result.filename}`;
    } else if (kind === "delete-course") {
      message = (await api(`/api/courses/${id}`, "DELETE")).message;
    } else {
      await api(`/api/${course ? "courses" : "users"}${id ? "/" + id : ""}`, id ? "PUT" : "POST", data);
    }
    $("#editor").close();
    await navigate(kind === "attendance-roll-call" ? "attendance" : state.view);
    notify(message);
  } catch (error) { $("#editor-error").textContent = error.message; }
  finally { button.disabled = false; }
});

function validateFile(file) {
  if (!file) return "請選擇檔案。";
  if (!/\.(pdf|png|jpe?g|txt)$/i.test(file.name)) return "請選擇 PDF、PNG、JPG 或 TXT 檔案。";
  if (file.size > 10 * 1024 * 1024) return "檔案超過 10 MB，請重新選擇。";
  if (!file.size) return "檔案沒有內容，請重新選擇。";
  return "";
}

$("#editor-form").addEventListener("change", event => {
  if (event.target.name !== "file") return;
  const file = event.target.files[0];
  const error = validateFile(file);
  $("#editor-error").textContent = error;
  $("#file-preview").textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : "尚未選擇檔案";
  event.currentTarget.querySelector('button[type="submit"]').disabled = !!error;
});

function setPasswordVisible(show) {
  const field = $("#login-password");
  field.type = show ? "text" : "password";
  $("#toggle-password").textContent = show ? "隱藏" : "顯示";
  $("#toggle-password").setAttribute("aria-pressed", String(show));
}

$("#toggle-password").addEventListener("click", () => {
  setPasswordVisible($("#login-password").type === "password");
});

$("#content").addEventListener("toggle", () => {
  const button = $('[data-action="toggle-groups"]');
  if (button) button.textContent = [...document.querySelectorAll(".feature-group")].every(g => g.open) ? "全部收合" : "全部展開";
}, true);

AttendanceModule.configure({api, escape, table, input, openEditor, user: () => state.user,
  refreshClasses: async () => { if (state.view === "attendance") await navigate("attendance"); }});

(async () => {
  try { await showPortal(await api("/api/me")); }
  catch (error) {
    showLogin();
    if (!/^(請先登入|登入已失效)/.test(error.message)) $("#login-error").textContent = error.message;
  }
})();
