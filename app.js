/* =====================================================
   HRMS – Auto Clock-In / Clock-Out  |  app.js
   ===================================================== */

// ─── Constants ────────────────────────────────────────
const MS_PER_DAY = 86_400_000;

// ─── Seed Data ────────────────────────────────────────
// Salary data is kept in-memory only and never persisted to localStorage.
const SEED_EMPLOYEES = [
  { id: 1, name: "John Doe",     dept: "Engineering", position: "Senior Dev",      email: "john@hrms.io"   },
  { id: 2, name: "Jane Smith",   dept: "Marketing",   position: "Marketing Lead",  email: "jane@hrms.io"   },
  { id: 3, name: "Carlos Reyes", dept: "HR",          position: "HR Manager",      email: "carlos@hrms.io" },
  { id: 4, name: "Aisha Patel",  dept: "Finance",     position: "Accountant",      email: "aisha@hrms.io"  },
  { id: 5, name: "Tom Lee",      dept: "Operations",  position: "Ops Coordinator", email: "tom@hrms.io"    },
];

// Salary lookup kept in-memory only (not persisted).
const salaryMap = {
  1: 5000, 2: 4200, 3: 3800, 4: 3500, 5: 3200,
};

const SEED_LEAVES = [
  { id: 1, empId: 2, type: "Annual",    from: "2026-04-10", to: "2026-04-12", days: 3, status: "Approved" },
  { id: 2, empId: 4, type: "Sick",      from: "2026-04-07", to: "2026-04-07", days: 1, status: "Pending"  },
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

// ─── Utilities ────────────────────────────────────────
const todayStr = () => new Date().toISOString().slice(0, 10);
const fmtTime  = (iso) => iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "–";
const MS_PER_HOUR = 3_600_000;
const fmtHours = (inIso, outIso) => {
  if (!inIso || !outIso) return "–";
  const diff = (new Date(outIso) - new Date(inIso)) / MS_PER_HOUR;
  return diff.toFixed(1) + "h";
};
const statusBadge = (status) => {
  const map = { Present: "success", Absent: "danger", Late: "warning", "On Leave": "info", Pending: "warning", Approved: "success", Rejected: "danger" };
  return `<span class="badge badge-${map[status] || "gray"}">${status}</span>`;
};
const empName = (id) => (employees.find(e => e.id === id) || {}).name || "Unknown";

// ─── Live clock ───────────────────────────────────────
function updateClocks() {
  const now  = new Date();
  const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const date = now.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });

  const bigClock = document.getElementById("big-clock");
  const dateLabel = document.getElementById("date-label");
  const clockDisplay = document.getElementById("clock-display");

  if (bigClock) bigClock.textContent = time;
  if (dateLabel) dateLabel.textContent = date;
  if (clockDisplay) clockDisplay.textContent = time;
}
setInterval(updateClocks, 1000);
updateClocks();

// ─── Page navigation ──────────────────────────────────
const pages   = document.querySelectorAll(".page");
const navLinks = document.querySelectorAll(".nav-link");
const pageTitle = document.getElementById("page-title");
const sidebar   = document.getElementById("sidebar");

function showPage(name) {
  pages.forEach(p => p.classList.toggle("active", p.id === `page-${name}`));
  navLinks.forEach(l => l.classList.toggle("active", l.dataset.page === name));
  const titles = { dashboard: "Dashboard", clock: "Clock In / Out", attendance: "Attendance", employees: "Employees", leaves: "Leave Management", payroll: "Payroll" };
  pageTitle.textContent = titles[name] || name;
  renderPage(name);
  // close sidebar on mobile
  sidebar.classList.remove("open");
}

navLinks.forEach(l => l.addEventListener("click", e => { e.preventDefault(); showPage(l.dataset.page); }));

document.getElementById("menu-btn").addEventListener("click", () => sidebar.classList.toggle("open"));

// ─── Render dispatcher ────────────────────────────────
function renderPage(name) {
  const fn = { dashboard: renderDashboard, clock: renderClock, attendance: renderAttendance, employees: renderEmployees, leaves: renderLeaves, payroll: renderPayroll };
  if (fn[name]) fn[name]();
}

// ─── Dashboard ────────────────────────────────────────
function renderDashboard() {
  const today     = todayStr();
  const todayRecs = attendance.filter(r => r.date === today);
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
  tbody.innerHTML = employees.map(emp => {
    const rec = todayRecs.find(r => r.empId === emp.id);
    const onLeave = leaveIds.includes(emp.id);
    const status = rec ? "Present" : onLeave ? "On Leave" : "Absent";
    return `<tr>
      <td>${emp.name}</td>
      <td>${rec ? fmtTime(rec.clockIn) : "–"}</td>
      <td>${rec ? fmtTime(rec.clockOut) : "–"}</td>
      <td>${statusBadge(status)}</td>
    </tr>`;
  }).join("");
}

// ─── Clock In/Out ─────────────────────────────────────
function renderClock() {
  const sel = document.getElementById("clock-employee");
  sel.innerHTML = `<option value="">-- Select Employee --</option>` +
    employees.map(e => `<option value="${e.id}">${e.name}</option>`).join("");
}

document.getElementById("btn-clockin").addEventListener("click", () => {
  const sel = document.getElementById("clock-employee");
  const empId = parseInt(sel.value, 10);
  if (!empId) { setClockStatus("Please select an employee.", "var(--danger)"); return; }

  const today = todayStr();
  const existing = attendance.find(r => r.empId === empId && r.date === today);
  if (existing) { setClockStatus(`${empName(empId)} has already clocked in today.`, "var(--warning)"); return; }

  const rec = { id: Date.now(), empId, date: today, clockIn: new Date().toISOString(), clockOut: null };
  attendance.push(rec);
  save("hrms_attendance", attendance);
  setClockStatus(`✅ ${empName(empId)} clocked in at ${fmtTime(rec.clockIn)}`, "var(--success)");
});

document.getElementById("btn-clockout").addEventListener("click", () => {
  const sel = document.getElementById("clock-employee");
  const empId = parseInt(sel.value, 10);
  if (!empId) { setClockStatus("Please select an employee.", "var(--danger)"); return; }

  const today = todayStr();
  const rec = attendance.find(r => r.empId === empId && r.date === today && !r.clockOut);
  if (!rec) { setClockStatus(`No active clock-in found for ${empName(empId)}.`, "var(--warning)"); return; }

  rec.clockOut = new Date().toISOString();
  save("hrms_attendance", attendance);
  setClockStatus(`🛑 ${empName(empId)} clocked out at ${fmtTime(rec.clockOut)} (${fmtHours(rec.clockIn, rec.clockOut)})`, "var(--danger)");
});

function setClockStatus(msg, color) {
  const el = document.getElementById("clock-status");
  el.textContent = msg;
  el.style.color = color;
}

// ─── Attendance ───────────────────────────────────────
function renderAttendance() {
  const filter = document.getElementById("att-filter-date").value;
  const records = filter ? attendance.filter(r => r.date === filter) : attendance;
  const tbody = document.getElementById("att-tbody");
  if (!records.length) { tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-light);padding:20px">No records found.</td></tr>`; return; }

  tbody.innerHTML = [...records].reverse().map(r => {
    const status = r.clockOut ? "Present" : "Incomplete";
    return `<tr>
      <td>${empName(r.empId)}</td>
      <td>${r.date}</td>
      <td>${fmtTime(r.clockIn)}</td>
      <td>${fmtTime(r.clockOut)}</td>
      <td>${fmtHours(r.clockIn, r.clockOut)}</td>
      <td>${statusBadge(status)}</td>
    </tr>`;
  }).join("");
}

document.getElementById("att-filter-btn").addEventListener("click", renderAttendance);

// ─── Employees ────────────────────────────────────────
function renderEmployees() {
  const tbody = document.getElementById("emp-tbody");
  tbody.innerHTML = employees.map(e =>
    `<tr>
      <td>#${e.id}</td>
      <td>${e.name}</td>
      <td>${e.dept}</td>
      <td>${e.position}</td>
      <td>${e.email}</td>
      <td>
        <button class="btn btn-sm btn-danger" onclick="deleteEmployee(${e.id})">Delete</button>
      </td>
    </tr>`
  ).join("");
}

document.getElementById("add-emp-btn").addEventListener("click", () => openModal("emp-modal"));
document.getElementById("emp-cancel").addEventListener("click", () => closeModal("emp-modal"));
document.getElementById("emp-save").addEventListener("click", () => {
  const name   = document.getElementById("emp-name").value.trim();
  const dept   = document.getElementById("emp-dept").value;
  const pos    = document.getElementById("emp-pos").value.trim();
  const email  = document.getElementById("emp-email").value.trim();
  const salary = parseFloat(document.getElementById("emp-salary").value) || 3000;
  if (!name || !pos || !email) { alert("Please fill in all fields."); return; }
  // Salary is stored in-memory only, not persisted to localStorage.
  employees.push({ id: nextEmpId, name, dept, position: pos, email });
  salaryMap[nextEmpId] = salary;
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

// ─── Leaves ───────────────────────────────────────────
function renderLeaves() {
  const tbody = document.getElementById("leaves-tbody");
  tbody.innerHTML = leaves.map(l => {
    const from = new Date(l.from), to = new Date(l.to);
    const days = Math.round((to - from) / MS_PER_DAY) + 1;
    return `<tr>
      <td>${empName(l.empId)}</td>
      <td>${l.type}</td>
      <td>${l.from}</td>
      <td>${l.to}</td>
      <td>${days}</td>
      <td>${statusBadge(l.status)}</td>
      <td>
        ${l.status === "Pending" ? `<button class="btn btn-sm btn-success" onclick="setLeaveStatus(${l.id},'Approved')">Approve</button>
        <button class="btn btn-sm btn-danger" style="margin-left:4px" onclick="setLeaveStatus(${l.id},'Rejected')">Reject</button>` : ""}
      </td>
    </tr>`;
  }).join("");
}

document.getElementById("add-leave-btn").addEventListener("click", () => {
  const sel = document.getElementById("leave-emp");
  sel.innerHTML = employees.map(e => `<option value="${e.id}">${e.name}</option>`).join("");
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

// ─── Payroll ──────────────────────────────────────────
function renderPayroll() {
  const today = todayStr();
  const month = today.slice(0, 7);
  const tbody = document.getElementById("payroll-tbody");

  tbody.innerHTML = employees.map(emp => {
    const monthRecs   = attendance.filter(r => r.empId === emp.id && r.date.startsWith(month) && r.clockOut);
    const daysPresent = monthRecs.length;
    const workDays    = 22;
    const baseSalary  = salaryMap[emp.id] ?? 0;
    const basePay     = (daysPresent / workDays) * baseSalary;
    const deductions  = basePay * 0.10;
    const netPay      = basePay - deductions;
    const fmt         = v => "$" + v.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

    return `<tr>
      <td>${emp.name}</td>
      <td>${emp.dept}</td>
      <td>${daysPresent} / ${workDays}</td>
      <td>${fmt(baseSalary)}</td>
      <td>${fmt(deductions)}</td>
      <td><strong>${fmt(netPay)}</strong></td>
    </tr>`;
  }).join("");
}

// ─── Modal helpers ────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.add("open");
}
function closeModal(id) {
  document.getElementById(id).classList.remove("open");
  // reset all form inputs and selects
  document.getElementById(id).querySelectorAll("input, select").forEach(el => {
    if (el.tagName === "SELECT") { el.selectedIndex = 0; }
    else { el.value = ""; }
  });
}

// ─── Bootstrap ────────────────────────────────────────
showPage("dashboard");
