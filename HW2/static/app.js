"use strict";
const $ = (selector) => document.querySelector(selector);
const roles = {admin: "管理員", administrative: "行政", student: "學生", teacher: "老師"};
const statuses = {pending: "待審核", approved: "已核准", rejected: "已駁回"};
const days = ["", "一", "二", "三", "四", "五", "六", "日"];
const state = {user: null, settings: {}, view: "courses", courses: [], users: [], keyword: "", generation: 0};
const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const period = (c) => `星期${days[c.weekday]} · 第 ${c.start_period}–${c.end_period} 節`;
const manager = () => ["admin", "administrative"].includes(state.user.role);

async function api(path, method = "GET", body) {
  const response = await fetch(path, {method, credentials: "same-origin", headers: {"Content-Type": "application/json", "X-Requested-With": "SchoolPortal"}, body: body === undefined ? undefined : JSON.stringify(body)});
  const result = await response.json();
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
  if ($("#editor").open) $("#editor").close();
}

async function showPortal(user) {
  state.user = user;
  state.settings = await api("/api/settings");
  $("#login-view").hidden = true;
  $("#portal").hidden = false;
  $("#identity").textContent = `${user.full_name} · ${roles[user.role]}`;
  updateHeading();
  const items = [["courses", "課程查詢"], ["schedule", user.role === "student" ? "我的課表" : user.role === "teacher" ? "授課課表" : "全校課表"], ["leave", user.role === "student" ? "請假申請" : "請假審核"]];
  if (user.role === "admin") items.push(["users", "使用者管理"], ["settings", "系統設定"], ["audit", "操作紀錄"]);
  items.push(["modules", "功能擴充"]);
  $("#navigation").innerHTML = items.map(([id, title]) => `<button data-view="${id}">${title}</button>`).join("");
  await navigate("courses");
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
  document.querySelectorAll("nav button").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  $("#page-title").textContent = document.querySelector(`nav button[data-view="${view}"]`)?.textContent || "校務系統";
  $("#content").innerHTML = '<div class="empty">載入中…</div>';
  try {
    let html;
    if (view === "courses") html = await courseView();
    else if (view === "schedule") html = await scheduleView();
    else if (view === "leave") html = await leaveView();
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

async function courseView() {
  const courses = await api(`/api/courses?q=${encodeURIComponent(state.keyword)}`);
  state.courses = courses;
  const rows = courses.map(c => `<tr><td><strong>${escape(c.name)}</strong><small>${escape(c.code)} · ${c.credits} 學分</small></td><td>${escape(c.teacher_name)}</td><td>${period(c)}<small>${escape(c.room)}</small></td><td>${c.enrolled_count} / ${c.capacity}</td><td>${state.user.role === "student" ? `<button data-action="${c.enrolled ? "withdraw" : "enroll"}" data-id="${c.id}" ${state.settings.enrollment_open !== "true" || (!c.enrolled && c.enrolled_count >= c.capacity) ? "disabled" : ""} class="${c.enrolled ? "secondary" : ""}">${c.enrolled ? "退選" : c.enrolled_count >= c.capacity ? "已額滿" : "選課"}</button>` : manager() ? `<button class="secondary" data-action="edit-course" data-id="${c.id}">編輯</button><button class="danger" data-action="delete-course" data-id="${c.id}">刪除</button>` : '<span class="muted">授課資訊</span>'}</td></tr>`);
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
  const rows = items.map(l => `<tr><td>#${l.id}<small>${escape(l.student_name)}</small></td><td>${escape(l.start_date)}<br>至 ${escape(l.end_date)}</td><td>${escape(l.reason)}</td><td><span class="badge ${l.status}">${statuses[l.status]}</span><small>${escape(l.reviewer_name || "")}</small></td><td>${!student && l.status === "pending" ? `<button data-action="approved" data-id="${l.id}">核准</button><button class="danger" data-action="rejected" data-id="${l.id}">駁回</button>` : "—"}</td></tr>`);
  const today = new Date();
  const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
  const form = student ? `<div class="card card-body form-card"><h2>新增請假申請</h2><form id="leave-form"><div class="grid-2"><label>開始日期<input type="date" name="start_date" value="${localDate}" required></label><label>結束日期<input type="date" name="end_date" value="${localDate}" required></label></div><label>請假原因<textarea name="reason" required maxlength="1000" placeholder="請說明請假原因"></textarea></label><button>送出申請</button></form></div>` : `<p class="muted">待審核申請：${items.filter(l => l.status === "pending").length} 筆</p>`;
  return form + table(["編號 / 學生", "請假日期", "原因", "狀態 / 審核人", "操作"], rows);
}

async function userView() {
  const users = await api("/api/users");
  state.users = users;
  return `<div class="toolbar"><p class="muted">管理校務帳號與角色權限</p><button data-action="new-user">新增使用者</button></div>${table(["姓名", "帳號", "角色", "狀態", "操作"], users.map(u => `<tr><td>${escape(u.full_name)}</td><td>${escape(u.username)}</td><td>${roles[u.role]}</td><td><span class="badge ${u.active ? "approved" : "rejected"}">${u.active ? "啟用" : "停用"}</span></td><td><button class="secondary" data-action="edit-user" data-id="${u.id}">編輯</button></td></tr>`))}`;
}

function settingsView() {
  return `<div class="card card-body form-card"><h2>校務設定</h2><form id="settings-form"><label>學校名稱<input name="school_name" maxlength="80" required value="${escape(state.settings.school_name)}"></label><label>學期<input name="semester" maxlength="80" required value="${escape(state.settings.semester)}"></label><label><input type="checkbox" name="enrollment_open" ${state.settings.enrollment_open === "true" ? "checked" : ""}>開放選課與退選</label><button>儲存設定</button></form></div><div class="card card-body form-card"><h2>資料庫備份</h2><p class="muted">建立目前資料庫的完整副本，保存在伺服器的資料目錄。</p><button data-action="backup">建立備份</button></div>`;
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
  $("#editor-title").textContent = title;
  $("#editor-error").textContent = "";
  const form = $("#editor-form");
  form.innerHTML = html;
  form.dataset.kind = kind;
  form.dataset.id = id || "";
  $("#editor").showModal();
}

$("#login-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.target.querySelector("button");
  button.disabled = true;
  $("#login-error").textContent = "";
  try {
    const result = await api("/api/login", "POST", Object.fromEntries(new FormData(event.target)));
    event.target.reset();
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
  if (event.target.dataset.view) navigate(event.target.dataset.view);
});

$("#content").addEventListener("click", async event => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const action = button.dataset.action, id = Number(button.dataset.id);
  button.disabled = true;
  try {
    if (action === "new-course" || action === "edit-course") return await editCourse(id || undefined);
    if (action === "new-user" || action === "edit-user") return editUser(id || undefined);
    let result;
    if (action === "enroll") result = await api("/api/enroll", "POST", {course_id: id});
    if (action === "withdraw") result = await api(`/api/enroll/${id}`, "DELETE");
    if (action === "approved" || action === "rejected") result = await api(`/api/leave/${id}/review`, "POST", {status: action});
    if (action === "delete-course") {
      if (!window.confirm("確定刪除此課程？已有學生選課的課程無法刪除。")) return;
      result = await api(`/api/courses/${id}`, "DELETE");
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
  const data = Object.fromEntries(new FormData(form));
  const course = form.dataset.kind === "course";
  if (course) for (const key of ["teacher_id", "credits", "capacity", "weekday", "start_period", "end_period"]) data[key] = Number(data[key]);
  else {
    data.active = form.elements.active.checked;
    if (id && !data.password) delete data.password;
  }
  const button = form.querySelector("button");
  button.disabled = true;
  $("#editor-error").textContent = "";
  try {
    await api(`/api/${course ? "courses" : "users"}${id ? "/" + id : ""}`, id ? "PUT" : "POST", data);
    $("#editor").close();
    await navigate(state.view);
    notify("儲存成功");
  } catch (error) { $("#editor-error").textContent = error.message; }
  finally { button.disabled = false; }
});

(async () => {
  try { await showPortal(await api("/api/me")); }
  catch (error) {
    showLogin();
    if (!/登入/.test(error.message)) $("#login-error").textContent = error.message;
  }
})();
