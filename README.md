# Momentum — Habit & Task Tracker

A full-stack habit and to-do tracker with streak tracking, daily points, and progress charts.

## Project Structure

```
habit-tracker/
├── backend/
│   ├── server.py       ← Combined Flask server (API + serves frontend)
│   ├── app.py          ← API-only version (if you use a separate dev server)
│   ├── database.py     ← SQLite schema + connection helper
│   ├── requirements.txt
│   └── tracker.db      ← Created automatically on first run
└── frontend/
    ├── index.html
    └── static/
        ├── css/style.css
        └── js/app.js
```

## Quick Start

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Run the server
python server.py

# 3. Open your browser
# http://127.0.0.1:5000
```

---

## How It Works — Step by Step

### 1. Database (SQLite — `database.py`)

Three tables:

| Table | Purpose |
|---|---|
| `items` | Stores habits and tasks |
| `daily_logs` | Tracks per-day completion for habits |
| `daily_points` | Aggregates points per day for the graph |

**Why separate `daily_logs`?**  
Tasks are one-time (completed flag lives on the item itself), but habits reset every day. `daily_logs` stores one row per habit per day, enabling streak calculation and daily graph data.

---

### 2. Backend REST API (`server.py`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/items` | Fetch all habits + tasks |
| POST | `/api/items` | Add a new habit or task |
| DELETE | `/api/items/<id>` | Delete an item |
| POST | `/api/items/<id>/toggle` | Mark complete/incomplete |
| GET | `/api/stats?days=7` | Points history for graph |
| GET | `/api/today-summary` | Today's habit + task points |

**Toggle logic:**
- **Habit** → inserts/updates `daily_logs` for today; adjusts `daily_points`
- **Task** → flips `completed` on the item itself; adjusts `daily_points`
- Points are never negative (clamped to 0 on uncheck)

---

### 3. Streak Calculation

```python
def calculate_streak(db, item_id):
    # Walk backwards from today
    # As long as each previous day was completed → increment streak
    # First gap → stop
```

The streak resets if a day is missed — motivating daily consistency.

---

### 4. Frontend (`app.js`)

- **`loadAll()`** — called on boot and after every action; refreshes items, scores, and chart
- **`renderList()`** — builds HTML for each item card dynamically
- **`toggleItem()`** → POST `/toggle` → `loadAll()`
- **`submitItem()`** → POST `/items` → `loadAll()`
- **`loadChart()`** → GET `/stats` → Chart.js line chart

The chart uses `fill: true` and `tension: 0.4` for smooth area curves, with custom dark-theme colors.

---

### 5. Points System

- Every toggle-to-complete → +1 point (habit or task)
- Toggle-to-incomplete → -1 point (never below 0)
- Points are stored daily in `daily_points` table
- Graph shows last 7/14/30 days of both habit and task points

---

### 6. Streak Tracking (Bonus ✓)

Each habit card shows a 🔥 streak badge. The streak counts consecutive days where the habit was marked complete, walking backwards from today.

---

## Design Decisions

- **SQLite** — zero config, file-based, perfect for local/personal apps
- **Flask** serves both API and static files — single command to run everything
- **Chart.js** — lightweight, no build step needed, rich customization
- **Vanilla JS** — no framework required for this scope; keeps it simple

## Extending the App

- **Reset daily progress**: Add a cron job / scheduled task that calls a `/api/reset-day` endpoint each midnight to seed fresh `daily_logs` rows for all habits
- **User accounts**: Add a `users` table and associate items with user IDs
- **Categories/tags**: Add a `category` column to `items`
- **Notifications**: Use browser Notifications API to remind users to complete habits
