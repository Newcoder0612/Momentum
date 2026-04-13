/* ── Config ── */
const API = "http://127.0.0.1:5000/api";

/* ── State ── */
let currentType = "habit";
let chart       = null;
let chartDays   = 7;

/* ── Boot ── */
document.addEventListener("DOMContentLoaded", async () => {
  // First: check if user is logged in
  // If not, redirect to login page immediately
  await checkAuth();

  // Date badge
  const opts = { weekday: "long", month: "long", day: "numeric" };
  document.getElementById("dateBadge").textContent =
    new Date().toLocaleDateString("en-US", opts).toUpperCase();

  // Range tabs
  document.querySelectorAll(".range-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".range-tab").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      chartDays = Number(btn.dataset.days);
      loadChart();
    });
  });

  loadAll();
});

/* ── Auth check ──────────────────────────────────────────────────────────────
   Called on every page load.
   Asks the server "who am I?" — if not logged in, go to login page.
   credentials:"include" sends the session cookie along with the request.
*/
async function checkAuth() {
  try {
    const res = await fetch(`${API}/me`, { credentials: "include" });
    if (!res.ok) {
      window.location.href = "/login";
      return;
    }
    const data = await res.json();
    const el = document.getElementById("welcomeText");
    if (el) el.textContent = `Hi, ${data.username}`;
  } catch {
    window.location.href = "/login";
  }
}

/* ── Logout ── */
async function logout() {
  await fetch(`${API}/logout`, { method: "POST", credentials: "include" });
  window.location.href = "/login";
}

/* ── API helper ── */
async function api(path, method = "GET", body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include"   // ← always send session cookie
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  // If session expired mid-session → go to login
  if (res.status === 401) { window.location.href = "/login"; return; }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/* ── Load everything ── */
async function loadAll() {
  await Promise.all([loadItems(), loadSummary(), loadChart()]);
}

async function loadItems() {
  const items  = await api("/items");
  const habits = items.filter(i => i.type === "habit");
  const tasks  = items.filter(i => i.type === "task");
  renderList("habitList", habits, "habit");
  renderList("taskList",  tasks,  "task");
}

async function loadSummary() {
  const { habit_points, task_points } = await api("/today-summary");
  setScore("habitPoints", habit_points);
  setScore("taskPoints",  task_points);
}

function setScore(id, val) {
  const el   = document.getElementById(id);
  const prev = Number(el.textContent);
  el.textContent = val;
  if (val !== prev) {
    el.classList.remove("bump");
    requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add("bump")));
    setTimeout(() => el.classList.remove("bump"), 400);
  }
}

/* ── Render ── */
function renderList(listId, items, type) {
  const ul = document.getElementById(listId);
  if (!items.length) {
    ul.innerHTML = `<li class="empty-state">No ${type}s yet — add one!</li>`;
    return;
  }
  ul.innerHTML = items.map(item => itemHTML(item, type)).join("");
  ul.querySelectorAll(".check-btn").forEach(btn =>
    btn.addEventListener("click", () => toggleItem(Number(btn.dataset.id)))
  );
  ul.querySelectorAll(".delete-btn").forEach(btn =>
    btn.addEventListener("click", () => deleteItem(Number(btn.dataset.id)))
  );
}

function itemHTML(item, type) {
  const done        = item.completed_today;
  const streak      = item.streak || 0;
  const streakBadge = (type === "habit" && streak > 0)
    ? `<span class="streak-badge">🔥 ${streak}d</span>` : "";
  const metaText    = type === "habit"
    ? `Daily habit ${streakBadge}` : `One-time task`;
  return `
    <li class="item-card${done ? " completed" : ""}">
      <button class="check-btn" data-id="${item.id}">${done ? "✓" : ""}</button>
      <div class="item-info">
        <div class="item-name">${escHtml(item.name)}</div>
        <div class="item-meta">${metaText}</div>
      </div>
      <button class="delete-btn" data-id="${item.id}">✕</button>
    </li>`;
}

function escHtml(str) {
  return str.replace(/[&<>"']/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])
  );
}

/* ── Toggle / Delete ── */
async function toggleItem(id) {
  try { await api(`/items/${id}/toggle`, "POST"); await loadAll(); }
  catch { toast("Couldn't update item 😕"); }
}

async function deleteItem(id) {
  try { await api(`/items/${id}`, "DELETE"); await loadAll(); toast("Item deleted"); }
  catch { toast("Couldn't delete item 😕"); }
}

/* ── Modal ── */
function openModal(type) {
  currentType = type;
  document.getElementById("modalTitle").textContent  = type === "habit" ? "Add Habit" : "Add Task";
  document.getElementById("submitBtn").textContent   = type === "habit" ? "Add Habit" : "Add Task";
  document.getElementById("modalHint").textContent   = type === "habit"
    ? "Habits repeat daily and build streaks."
    : "Tasks are one-time items.";
  document.getElementById("itemNameInput").value = "";
  document.getElementById("modalBackdrop").classList.add("open");
  document.getElementById("addModal").classList.add("open");
  setTimeout(() => document.getElementById("itemNameInput").focus(), 50);
}

function closeModal() {
  document.getElementById("modalBackdrop").classList.remove("open");
  document.getElementById("addModal").classList.remove("open");
}

document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

async function submitItem() {
  const name = document.getElementById("itemNameInput").value.trim();
  if (!name) return;
  try {
    await api("/items", "POST", { name, type: currentType });
    closeModal();
    toast(`${currentType === "habit" ? "Habit" : "Task"} added! 🎉`);
    await loadAll();
  } catch { toast("Failed to add item 😕"); }
}

/* ── Chart ── */
async function loadChart() {
  const data     = await api(`/stats?days=${chartDays}`);
  const labels   = data.map(r => {
    const d = new Date(r.log_date + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  });
  const habitPts = data.map(r => r.habit_points);
  const taskPts  = data.map(r => r.task_points);
  const ctx      = document.getElementById("progressChart").getContext("2d");
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Habit Points", data: habitPts, borderColor: "#e8b86d",
          backgroundColor: "rgba(232,184,109,.12)", borderWidth: 2.5,
          pointBackgroundColor: "#e8b86d", pointRadius: 4, fill: true, tension: .4 },
        { label: "Task Points",  data: taskPts,  borderColor: "#7ec8a4",
          backgroundColor: "rgba(126,200,164,.1)",  borderWidth: 2.5,
          pointBackgroundColor: "#7ec8a4", pointRadius: 4, fill: true, tension: .4 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#a89f8c", font: { family: "'DM Sans'", size: 12 },
          usePointStyle: true } },
        tooltip: { backgroundColor: "#1e1c19", titleColor: "#f0e6d0",
          bodyColor: "#a89f8c", borderColor: "#3a3630", borderWidth: 1, padding: 12,
          callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y} pts` } },
      },
      scales: {
        x: { grid: { color: "rgba(60,56,50,.5)" },
             ticks: { color: "#5c564d", font: { family: "'DM Sans'", size: 11 } } },
        y: { beginAtZero: true, grid: { color: "rgba(60,56,50,.5)" },
             ticks: { color: "#5c564d", font: { family: "'DM Sans'", size: 11 }, stepSize: 1 } },
      },
    },
  });
}

/* ── Toast ── */
let toastTimer = null;
function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2500);
}
