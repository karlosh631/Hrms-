/* =====================================================
   HRMS – Horilla  |  app.js
   ===================================================== */

// ─── Constants ────────────────────────────────────────
const MS_PER_DAY  = 86_400_000;
const MS_PER_HOUR = 3_600_000;

// ─── Credential store ─────────────────────────────────
// Passwords are stored as plain text here for demo purposes only.
// In a production system these would be validated server-side.
const CREDENTIALS = {
  "ADMIN":  { password: "admin123",  role: "admin",    empId: null },
  "EMP001": { password: "hrms1234",  role: "employee", empId: 1    },
  "EMP002": { password: "hrms1234",  role: "employee", empId: 2    },
  "EMP003": { password: "hrms1234",  role: "employee", empId: 3    },
  "EMP004": { password: "hrms1234",  role: "employee", empId: 4    },
  "EMP005": { password: "hrms1234",  role: "employee", empId: 5    },
};

// ─── Seed Data ────────────────────────────────────────
const SEED_EMPLOYEES = [
  { id: 1, hrmsId: "EMP001", name: "John Doe",     dept: "Engineering", position: "Senior Dev",      email: "john@hrms.io"   },
  { id: 2, hrmsId: "EMP002", name: "Jane Smith",   dept: "Marketing",   position: "Marketing Lead",  email: "jane@hrms.io"   },
  { id: 3, hrmsId: "EMP003", name: "Carlos Reyes", dept: "HR",          position: "HR Manager",      email: "carlos@hrms.io" },
  { id: 4, hrmsId: "EMP004", name: "Aisha Patel",  dept: "Finance",     position: "Accountant",      email: "aisha@hrms.io"  },
  { id: 5, hrmsId: "EMP005", name: "Tom Lee",      dept: "Operations",  position: "Ops Coordinator", email: "tom@hrms.io"    },
];

// Salary kept in-memory only — never persisted.
const salaryMap = { 1: 5000, 2: 4200, 3: 3800, 4: 3500, 5: 3200 };

const SEED_LEAVES = [
  { id: 1, empId: 2, type: "Annual", from: "2026-04-10", to: "2026-04-12", status: "Approved" },
  { id: 2, empId: 4, type: "Sick",   from: "2026-04-07", to: "2026-04-07", status: "Pending"  },
];

// ─── LocalStorage helpers ─────────────────────────────
function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}
function save(key, val) { localStorage.setItem(key, JSON.stringify(val)); }

// ─── State ────────────────────────────────────────────
let employees  = load("hrms_employees",  SEED_EMPLOYEES);
let attendance = load("hrms_attendance", []);
let leaves     = load("hrms_leaves",     SEED_LEAVES);
let nextEmpId  = load("hrms_nextEmpId",  SEED_EMPLOYEES.length + 1);

// ─── Session ──────────────────────────────────────────
// currentUser is stored only for this tab (sessionStorage).
let currentUser = null;

function loadSession() {
  try {
    const raw = sessionStorage.getItem("hrms_session");
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveSession(user) {
  sessionStorage.setItem("hrms_session", JSON.stringify(user));
}

function clearSession() {
  sessionStorage.removeItem("hrms_session");
}

// ─── Utilities ────────────────────────────────────────
const todayStr = () => new Date().toISOString().slice(0, 10);
const fmtTime  = (iso) => iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "–";
const fmtHours = (inIso, outIso) => {
  if (!inIso || !outIso) return "–";
  return ((new Date(outIso) - new Date(inIso)) / MS_PER_HOUR).toFixed(1) + "h";
};

// Escape user-supplied strings before inserting into innerHTML.
function escHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Generate a zero-padded HRMS employee ID.
const genHrmsId = (n) => `EMP${String(n).padStart(3, "0")}`;

// Format a dollar amount with comma separators.
const fmtCurrency = (v) => "$" + v.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

// Compute leave days using UTC dates to avoid DST issues.
function leaveDays(fromStr, toStr) {
  const from = Date.UTC(...fromStr.split("-").map((v, i) => i === 1 ? +v - 1 : +v));
  const to   = Date.UTC(...toStr.split("-").map((v, i)  => i === 1 ? +v - 1 : +v));
  return Math.round((to - from) / MS_PER_DAY) + 1;
}

const statusBadge = (status) => {
  const map = {
    Present: "success", Absent: "danger", Late: "warning",
    "On Leave": "info", Incomplete: "warning",
    Pending: "warning", Approved: "success", Rejected: "danger",
  };
  return `<span class="badge badge-${map[status] || "gray"}">${escHtml(status)}</span>`;
};
const empName = (id) => (employees.find(e => e.id === id) || {}).name || "Unknown";
const initials = (name) => name ? name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase() : "?";

// ─── Live clock ───────────────────────────────────────
function updateClocks() {
  const now  = new Date();
  const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const date = now.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  const el1 = document.getElementById("big-clock");
  const el2 = document.getElementById("date-label");
  const el3 = document.getElementById("clock-display");
  if (el1) el1.textContent = time;
  if (el2) el2.textContent = date;
  if (el3) el3.textContent = time;
}
setInterval(updateClocks, 1000);
updateClocks();

// ─── LOGIN ────────────────────────────────────────────
const loginScreen = document.getElementById("login-screen");
const appShell    = document.getElementById("app-shell");

function tryLogin() {
  const hrmsId   = document.getElementById("login-id").value.trim().toUpperCase();
  const password = document.getElementById("login-pass").value;
  const errEl    = document.getElementById("login-error");

  const cred = CREDENTIALS[hrmsId];
  if (!cred || cred.password !== password) {
    errEl.textContent = "Invalid HRMS ID or password. Please try again.";
    document.getElementById("login-pass").value = "";
    return;
  }

  errEl.textContent = "";
  const emp = cred.empId ? employees.find(e => e.id === cred.empId) : null;
  currentUser = { hrmsId, role: cred.role, empId: cred.empId, name: emp ? emp.name : "Administrator" };
  saveSession(currentUser);
  bootApp();
}

document.getElementById("btn-login").addEventListener("click", tryLogin);
document.getElementById("login-pass").addEventListener("keydown", e => { if (e.key === "Enter") tryLogin(); });
document.getElementById("login-id").addEventListener("keydown", e => { if (e.key === "Enter") document.getElementById("login-pass").focus(); });

// Password visibility toggle
document.getElementById("pass-toggle").addEventListener("click", () => {
  const inp = document.getElementById("login-pass");
  inp.type = inp.type === "password" ? "text" : "password";
});

// ─── Logout ───────────────────────────────────────────
document.getElementById("btn-logout").addEventListener("click", () => {
  clearSession();
  currentUser = null;
  appShell.classList.add("hidden");
  loginScreen.classList.remove("hidden");
  document.getElementById("login-id").value = "";
  document.getElementById("login-pass").value = "";
  document.getElementById("login-error").textContent = "";
});

// ─── Boot the app after login ─────────────────────────
function bootApp() {
  loginScreen.classList.add("hidden");
  appShell.classList.remove("hidden");

  const isAdmin = currentUser.role === "admin";

  // Update sidebar user info
  document.getElementById("sidebar-avatar").textContent = initials(currentUser.name);
  document.getElementById("sidebar-name").textContent   = currentUser.name;
  document.getElementById("sidebar-role").textContent   = isAdmin ? "Administrator" : currentUser.hrmsId;
  document.getElementById("topbar-avatar").textContent  = initials(currentUser.name);

  // Show/hide admin-only nav items
  document.querySelectorAll(".admin-only").forEach(el => {
    el.style.display = isAdmin ? "" : "none";
  });

  // Update bottom nav: show/hide admin items
  document.querySelectorAll(".bnav-link").forEach(l => {
    const page = l.dataset.page;
    if (!isAdmin && (page === "employees" || page === "payroll")) {
      l.style.display = "none";
    }
  });

  showPage("dashboard");
}

// ─── Page navigation ──────────────────────────────────
const pages     = document.querySelectorAll(".page");
const navLinks  = document.querySelectorAll(".nav-link");
const bnavLinks = document.querySelectorAll(".bnav-link");
const pageTitle = document.getElementById("page-title");
const sidebar   = document.getElementById("sidebar");
const backdrop  = document.getElementById("sidebar-backdrop");

function showPage(name) {
  pages.forEach(p => p.classList.toggle("active", p.id === `page-${name}`));
  navLinks.forEach(l  => l.classList.toggle("active", l.dataset.page === name));
  bnavLinks.forEach(l => l.classList.toggle("active", l.dataset.page === name));
  const titles = {
    dashboard: "Dashboard", profile: "My Profile", clock: "Clock In / Out",
    attendance: "Attendance", employees: "Employees", leaves: "Leave Management", payroll: "Payroll",
  };
  pageTitle.textContent = titles[name] || name;
  renderPage(name);
  closeSidebar();
}

navLinks.forEach(l  => l.addEventListener("click", e => { e.preventDefault(); showPage(l.dataset.page); }));
bnavLinks.forEach(l => l.addEventListener("click", e => { e.preventDefault(); showPage(l.dataset.page); }));

document.getElementById("menu-btn").addEventListener("click", () => {
  sidebar.classList.toggle("open");
  backdrop.classList.toggle("visible", sidebar.classList.contains("open"));
});

backdrop.addEventListener("click", closeSidebar);

function closeSidebar() {
  sidebar.classList.remove("open");
  backdrop.classList.remove("visible");
}

// ─── Render dispatcher ────────────────────────────────
function renderPage(name) {
  const fn = {
    dashboard: renderDashboard, profile: renderProfile, clock: renderClock,
    attendance: renderAttendance, employees: renderEmployees, leaves: renderLeaves, payroll: renderPayroll,
  };
  if (fn[name]) fn[name]();
}

// ─── My Profile ───────────────────────────────────────
function renderProfile() {
  if (!currentUser) return;
  const emp = employees.find(e => e.id === currentUser.empId);
  if (!emp) {
    document.getElementById("profile-name").textContent = currentUser.name;
    document.getElementById("profile-position").textContent = "Administrator";
    document.getElementById("profile-dept").textContent = "";
    document.getElementById("profile-email").textContent = "";
    document.getElementById("profile-hrms-id").textContent = currentUser.hrmsId;
    document.getElementById("profile-avatar-big").textContent = initials(currentUser.name);
    document.getElementById("profile-days").textContent = "–";
    document.getElementById("profile-hours").textContent = "–";
    document.getElementById("profile-pending-leaves").textContent = "–";
    document.getElementById("profile-att-tbody").innerHTML = "";
    return;
  }

  document.getElementById("profile-avatar-big").textContent = initials(emp.name);
  document.getElementById("profile-name").textContent       = emp.name;
  document.getElementById("profile-position").textContent   = emp.position;
  document.getElementById("profile-dept").textContent       = emp.dept;
  document.getElementById("profile-email").textContent      = emp.email;
  document.getElementById("profile-hrms-id").textContent    = emp.hrmsId || currentUser.hrmsId;

  const month    = todayStr().slice(0, 7);
  const myRecs   = attendance.filter(r => r.empId === emp.id && r.date.startsWith(month));
  const daysPresent = myRecs.filter(r => r.clockOut).length;
  const totalHours  = myRecs.reduce((sum, r) => {
    if (!r.clockIn || !r.clockOut) return sum;
    return sum + (new Date(r.clockOut) - new Date(r.clockIn)) / MS_PER_HOUR;
  }, 0);
  const pendingLeaves = leaves.filter(l => l.empId === emp.id && l.status === "Pending").length;

  document.getElementById("profile-days").textContent           = daysPresent;
  document.getElementById("profile-hours").textContent          = totalHours.toFixed(1) + "h";
  document.getElementById("profile-pending-leaves").textContent = pendingLeaves;

  const tbody = document.getElementById("profile-att-tbody");
  const recent = [...attendance].filter(r => r.empId === emp.id).reverse().slice(0, 10);
  if (!recent.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-light);padding:16px">No attendance records yet.</td></tr>`;
  } else {
    tbody.innerHTML = recent.map(r => `<tr>
      <td>${escHtml(r.date)}</td>
      <td>${escHtml(fmtTime(r.clockIn))}</td>
      <td>${escHtml(fmtTime(r.clockOut))}</td>
      <td>${escHtml(fmtHours(r.clockIn, r.clockOut))}</td>
      <td>${statusBadge(r.clockOut ? "Present" : "Incomplete")}</td>
    </tr>`).join("");
  }
}

// ─── Dashboard ────────────────────────────────────────
function renderDashboard() {
  const today      = todayStr();
  const todayRecs  = attendance.filter(r => r.date === today);
  const presentIds = todayRecs.map(r => r.empId);
  const leaveIds   = leaves.filter(l => l.status === "Approved" && l.from <= today && l.to >= today).map(l => l.empId);
  const presentCount = new Set(presentIds).size;
  const leaveCount   = new Set(leaveIds).size;
  const absentCount  = employees.length - presentCount - leaveCount;

  document.getElementById("stat-total").textContent   = employees.length;
  document.getElementById("stat-present").textContent = presentCount;
  document.getElementById("stat-absent").textContent  = Math.max(0, absentCount);
  document.getElementById("stat-leave").textContent   = leaveCount;

  const tbody = document.getElementById("today-tbody");
  const list  = currentUser.role === "admin" ? employees : employees.filter(e => e.id === currentUser.empId);
  tbody.innerHTML = list.map(emp => {
    const rec     = todayRecs.find(r => r.empId === emp.id);
    const onLeave = leaveIds.includes(emp.id);
    const status  = rec ? "Present" : onLeave ? "On Leave" : "Absent";
    return `<tr>
      <td>${escHtml(emp.name)}</td>
      <td>${escHtml(rec ? fmtTime(rec.clockIn) : "–")}</td>
      <td>${escHtml(rec ? fmtTime(rec.clockOut) : "–")}</td>
      <td>${statusBadge(status)}</td>
    </tr>`;
  }).join("");
}

// ─── Clock In/Out ─────────────────────────────────────
function renderClock() {
  const sel   = document.getElementById("clock-employee");
  const group = document.getElementById("clock-emp-group");
  const isAdmin = currentUser && currentUser.role === "admin";

  if (isAdmin) {
    group.style.display = "";
    sel.innerHTML = `<option value="">-- Select Employee --</option>` +
      employees.map(e => `<option value="${e.id}">${escHtml(e.name)} (${escHtml(e.hrmsId || "")})</option>`).join("");
  } else {
    // Auto-select the logged-in employee and hide the selector
    group.style.display = "none";
    sel.innerHTML = `<option value="${Number(currentUser.empId)}" selected></option>`;
  }
  setClockStatus("", "");
}

document.getElementById("btn-clockin").addEventListener("click", () => {
  const empId = getClockEmpId();
  if (!empId) { setClockStatus("No employee selected.", "var(--danger)"); return; }
  const today    = todayStr();
  const existing = attendance.find(r => r.empId === empId && r.date === today);
  if (existing) { setClockStatus(`${empName(empId)} has already clocked in today.`, "var(--warning)"); return; }
  const rec = { id: Date.now(), empId, date: today, clockIn: new Date().toISOString(), clockOut: null };
  attendance.push(rec);
  save("hrms_attendance", attendance);
  setClockStatus(`✅ ${empName(empId)} clocked in at ${fmtTime(rec.clockIn)}`, "var(--success)");
});

document.getElementById("btn-clockout").addEventListener("click", () => {
  const empId = getClockEmpId();
  if (!empId) { setClockStatus("No employee selected.", "var(--danger)"); return; }
  const today = todayStr();
  const rec   = attendance.find(r => r.empId === empId && r.date === today && !r.clockOut);
  if (!rec) { setClockStatus(`No active clock-in found for ${empName(empId)}.`, "var(--warning)"); return; }
  rec.clockOut = new Date().toISOString();
  save("hrms_attendance", attendance);
  setClockStatus(`🛑 ${empName(empId)} clocked out at ${fmtTime(rec.clockOut)} (${fmtHours(rec.clockIn, rec.clockOut)})`, "var(--danger)");
});

function getClockEmpId() {
  if (currentUser.role !== "admin") return currentUser.empId;
  return parseInt(document.getElementById("clock-employee").value, 10) || null;
}

function setClockStatus(msg, color) {
  const el = document.getElementById("clock-status");
  el.textContent = msg;
  if (color) {
    el.style.setProperty('color', color);
  } else {
    el.style.removeProperty('color');
  }
}

// ─── Attendance ───────────────────────────────────────
function renderAttendance() {
  const filter  = document.getElementById("att-filter-date").value;
  let records   = filter ? attendance.filter(r => r.date === filter) : attendance;
  if (currentUser.role !== "admin") {
    records = records.filter(r => r.empId === currentUser.empId);
  }
  const tbody = document.getElementById("att-tbody");
  if (!records.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-light);padding:20px">No records found.</td></tr>`;
    return;
  }
  tbody.innerHTML = [...records].reverse().map(r => `<tr>
    <td>${escHtml(empName(r.empId))}</td>
    <td>${escHtml(r.date)}</td>
    <td>${escHtml(fmtTime(r.clockIn))}</td>
    <td>${escHtml(fmtTime(r.clockOut))}</td>
    <td>${escHtml(fmtHours(r.clockIn, r.clockOut))}</td>
    <td>${statusBadge(r.clockOut ? "Present" : "Incomplete")}</td>
  </tr>`).join("");
}

document.getElementById("att-filter-btn").addEventListener("click", renderAttendance);

// ─── Employees ────────────────────────────────────────
function renderEmployees() {
  const tbody = document.getElementById("emp-tbody");
  tbody.innerHTML = employees.map(e => `<tr>
    <td>${escHtml(e.hrmsId || "#" + e.id)}</td>
    <td>${escHtml(e.name)}</td>
    <td>${escHtml(e.dept)}</td>
    <td>${escHtml(e.position)}</td>
    <td>${escHtml(e.email)}</td>
    <td>
      <button class="btn btn-sm btn-danger" data-delete-emp="${Number(e.id)}">Delete</button>
    </td>
  </tr>`).join("");
}

document.getElementById("add-emp-btn").addEventListener("click", () => openModal("emp-modal"));
document.getElementById("emp-cancel").addEventListener("click",  () => closeModal("emp-modal"));
document.getElementById("emp-save").addEventListener("click", () => {
  const name   = document.getElementById("emp-name").value.trim();
  const hrmsId = document.getElementById("emp-hrms-id").value.trim().toUpperCase();
  const dept   = document.getElementById("emp-dept").value;
  const pos    = document.getElementById("emp-pos").value.trim();
  const email  = document.getElementById("emp-email").value.trim();
  const salary = parseFloat(document.getElementById("emp-salary").value) || 3000;
  if (!name || !pos || !email) { alert("Please fill in all required fields."); return; }
  if (hrmsId && CREDENTIALS[hrmsId]) { alert("That HRMS ID is already taken."); return; }
  const newHrmsId = hrmsId || genHrmsId(nextEmpId);
  employees.push({ id: nextEmpId, hrmsId: newHrmsId, name, dept, position: pos, email });
  salaryMap[nextEmpId] = salary;
  // Register credentials for the new employee (demo only — production must use server-side auth).
  CREDENTIALS[newHrmsId] = { password: "hrms1234", role: "employee", empId: nextEmpId };
  nextEmpId++;
  save("hrms_employees", employees);
  save("hrms_nextEmpId", nextEmpId);
  closeModal("emp-modal");
  renderEmployees();
});

function deleteEmployee(id) {
  if (!confirm("Delete this employee?")) return;
  employees = employees.filter(e => e.id !== id);
  save("hrms_employees", employees);
  renderEmployees();
  renderDashboard();
}

// Delegated handler for the Delete button rendered inside #emp-tbody.
document.getElementById("emp-tbody").addEventListener("click", e => {
  const btn = e.target.closest("[data-delete-emp]");
  if (btn) deleteEmployee(Number(btn.dataset.deleteEmp));
});

// ─── Leaves ───────────────────────────────────────────
function renderLeaves() {
  const isAdmin = currentUser.role === "admin";
  const list    = isAdmin ? leaves : leaves.filter(l => l.empId === currentUser.empId);
  const tbody   = document.getElementById("leaves-tbody");

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-light);padding:20px">No leave records found.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(l => {
    const days = leaveDays(l.from, l.to);
    return `<tr>
      <td>${escHtml(empName(l.empId))}</td>
      <td>${escHtml(l.type)}</td>
      <td>${escHtml(l.from)}</td>
      <td>${escHtml(l.to)}</td>
      <td>${escHtml(days)}</td>
      <td>${statusBadge(l.status)}</td>
      <td>
        ${isAdmin && l.status === "Pending"
          ? `<button class="btn btn-sm btn-success" data-leave-id="${Number(l.id)}" data-leave-action="Approved">Approve</button>
             <button class="btn btn-sm btn-danger" style="margin-left:4px" data-leave-id="${Number(l.id)}" data-leave-action="Rejected">Reject</button>`
          : ""}
      </td>
    </tr>`;
  }).join("");
}

document.getElementById("add-leave-btn").addEventListener("click", () => {
  const empSel  = document.getElementById("leave-emp");
  const grp     = empSel.closest(".form-group");
  const isAdmin = currentUser.role === "admin";
  grp.style.display = isAdmin ? "" : "none";
  if (isAdmin) {
    empSel.innerHTML = employees.map(e => `<option value="${Number(e.id)}">${escHtml(e.name)}</option>`).join("");
  } else {
    empSel.innerHTML = `<option value="${Number(currentUser.empId)}" selected>${escHtml(empName(currentUser.empId))}</option>`;
  }
  openModal("leave-modal");
});

document.getElementById("leave-cancel").addEventListener("click", () => closeModal("leave-modal"));
document.getElementById("leave-save").addEventListener("click", () => {
  const empId = parseInt(document.getElementById("leave-emp").value, 10);
  const type  = document.getElementById("leave-type").value;
  const from  = document.getElementById("leave-from").value;
  const to    = document.getElementById("leave-to").value;
  if (!from || !to || to < from) { alert("Please choose valid dates."); return; }
  leaves.push({ id: Date.now(), empId, type, from, to, status: "Pending" });
  save("hrms_leaves", leaves);
  closeModal("leave-modal");
  renderLeaves();
});

function setLeaveStatus(id, status) {
  const rec = leaves.find(l => l.id === id);
  if (rec) { rec.status = status; save("hrms_leaves", leaves); renderLeaves(); }
}

// Delegated handler for the Approve/Reject buttons rendered inside #leaves-tbody.
document.getElementById("leaves-tbody").addEventListener("click", e => {
  const btn = e.target.closest("[data-leave-id]");
  if (btn) setLeaveStatus(Number(btn.dataset.leaveId), btn.dataset.leaveAction);
});

// ─── Payroll ──────────────────────────────────────────
function renderPayroll() {
  const month = todayStr().slice(0, 7);
  const tbody = document.getElementById("payroll-tbody");

  tbody.innerHTML = employees.map(emp => {
    const monthRecs   = attendance.filter(r => r.empId === emp.id && r.date.startsWith(month) && r.clockOut);
    const daysPresent = monthRecs.length;
    const workDays    = 22;
    const baseSalary  = salaryMap[emp.id] ?? 0;
    const basePay     = (daysPresent / workDays) * baseSalary;
    const deductions  = basePay * 0.10;
    const netPay      = basePay - deductions;

    return `<tr>
      <td>${escHtml(emp.name)}</td>
      <td>${escHtml(emp.dept)}</td>
      <td>${escHtml(daysPresent + " / " + workDays)}</td>
      <td>${escHtml(fmtCurrency(baseSalary))}</td>
      <td>${escHtml(fmtCurrency(deductions))}</td>
      <td><strong>${escHtml(fmtCurrency(netPay))}</strong></td>
    </tr>`;
  }).join("");
}

// ─── Modal helpers ────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.add("open");
}
function closeModal(id) {
  document.getElementById(id).classList.remove("open");
  document.getElementById(id).querySelectorAll("input, select").forEach(el => {
    el.tagName === "SELECT" ? (el.selectedIndex = 0) : (el.value = "");
  });
}

// ─── Bootstrap ────────────────────────────────────────
currentUser = loadSession();
if (currentUser) {
  bootApp();
} else {
  loginScreen.classList.remove("hidden");
  appShell.classList.add("hidden");
}
