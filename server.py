import sys, os, secrets
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, send_from_directory, jsonify, request, session
from flask_cors import CORS
from database import init_db, get_db
from email_sender import send_reset_email
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import functools

FRONTEND = os.path.join(os.path.dirname(__file__), "frontend")

app = Flask(__name__, static_folder=os.path.join(FRONTEND, "static"), static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")
CORS(app, supports_credentials=True)
init_db()


# ── Auth decorator ─────────────────────────────────────────────────────────────
def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return decorated

def current_user_id():
    return session["user_id"]


# ── Frontend + PWA routes ──────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" not in session:
        return send_from_directory(FRONTEND, "login.html")
    return send_from_directory(FRONTEND, "index.html")

@app.route("/login")
def login_page():
    return send_from_directory(FRONTEND, "login.html")

@app.route("/reset-password")
def reset_password_page():
    return send_from_directory(FRONTEND, "reset_password.html")

# PWA required files
@app.route("/manifest.json")
def manifest():
    return send_from_directory(FRONTEND, "manifest.json")

@app.route("/sw.js")
def service_worker():
    # Service workers must be served with this header
    # It tells the browser this SW controls the entire site (/)
    response = send_from_directory(FRONTEND, "sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response

@app.route("/static/icons/<path:filename>")
def icons(filename):
    return send_from_directory(os.path.join(FRONTEND, "static", "icons"), filename)


# ── Auth endpoints ─────────────────────────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
def register():
    data     = request.get_json()
    username = data.get("username", "").strip().lower()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if "@" not in email:
        return jsonify({"error": "Please enter a valid email address"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    hashed = generate_password_hash(password)
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (?,?,?,?)",
            (username, email, hashed, datetime.now().isoformat())
        )
        db.commit()
        user_id = cur.lastrowid
    except Exception as e:
        db.close()
        msg = str(e)
        if "username" in msg: return jsonify({"error": "Username already taken"}), 409
        if "email"    in msg: return jsonify({"error": "Email already registered"}), 409
        return jsonify({"error": "Registration failed"}), 409
    session["user_id"]  = user_id
    session["username"] = username
    db.close()
    return jsonify({"message": "Account created!", "username": username}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data     = request.get_json()
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    db  = get_db()
    row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    db.close()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401
    session["user_id"]  = row["id"]
    session["username"] = row["username"]
    return jsonify({"message": "Logged in!", "username": row["username"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"user_id": session["user_id"], "username": session["username"]})


# ── Password reset ─────────────────────────────────────────────────────────────
@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data  = request.get_json()
    email = data.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Please enter a valid email"}), 400
    db  = get_db()
    row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    success_msg = {"message": "If that email is registered, a reset link has been sent."}
    if not row:
        db.close()
        return jsonify(success_msg)
    token      = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(minutes=30)).isoformat()
    db.execute("DELETE FROM reset_tokens WHERE user_id=? AND used=0", (row["id"],))
    db.execute(
        "INSERT INTO reset_tokens (user_id, token, expires_at, used) VALUES (?,?,?,0)",
        (row["id"], token, expires_at)
    )
    db.commit()
    db.close()
    base_url   = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
    reset_link = f"{base_url}/reset-password?token={token}"
    send_reset_email(to_email=email, username=row["username"], reset_link=reset_link)
    return jsonify(success_msg)


@app.route("/api/verify-reset-token", methods=["POST"])
def verify_reset_token():
    data  = request.get_json()
    token = data.get("token", "").strip()
    if not token:
        return jsonify({"valid": False, "error": "No token provided"}), 400
    db  = get_db()
    row = db.execute(
        "SELECT * FROM reset_tokens WHERE token=? AND used=0", (token,)
    ).fetchone()
    db.close()
    if not row:
        return jsonify({"valid": False, "error": "Invalid or already used reset link"}), 400
    if datetime.now() > datetime.fromisoformat(row["expires_at"]):
        return jsonify({"valid": False, "error": "This reset link has expired. Please request a new one."}), 400
    return jsonify({"valid": True})


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data         = request.get_json()
    token        = data.get("token", "").strip()
    new_password = data.get("password", "")
    if not token:
        return jsonify({"error": "No token provided"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    db  = get_db()
    row = db.execute(
        "SELECT rt.*, u.username FROM reset_tokens rt "
        "JOIN users u ON u.id = rt.user_id "
        "WHERE rt.token=? AND rt.used=0", (token,)
    ).fetchone()
    if not row:
        db.close()
        return jsonify({"error": "Invalid or already used reset link"}), 400
    if datetime.now() > datetime.fromisoformat(row["expires_at"]):
        db.close()
        return jsonify({"error": "This link has expired. Please request a new one."}), 400
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (generate_password_hash(new_password), row["user_id"]))
    db.execute("UPDATE reset_tokens SET used=1 WHERE token=?", (token,))
    db.commit()
    session["user_id"]  = row["user_id"]
    session["username"] = row["username"]
    db.close()
    return jsonify({"message": "Password updated successfully!"})


# ── Helpers ────────────────────────────────────────────────────────────────────
def row_to_dict(row): return dict(row) if row else None
def today(): return date.today().isoformat()


# ── Items API ──────────────────────────────────────────────────────────────────
@app.route("/api/items", methods=["GET"])
@login_required
def get_items():
    uid   = current_user_id()
    db    = get_db()
    items = db.execute(
        "SELECT * FROM items WHERE user_id=? ORDER BY type, created_at DESC", (uid,)
    ).fetchall()
    result = []
    for item in items:
        d = row_to_dict(item)
        if d["type"] == "habit":
            log = db.execute(
                "SELECT completed FROM daily_logs WHERE item_id=? AND log_date=?",
                (d["id"], today())
            ).fetchone()
            d["completed_today"] = bool(log and log["completed"])
            d["streak"] = calculate_streak(db, d["id"])
        else:
            d["completed_today"] = bool(d["completed"])
            d["streak"] = 0
        result.append(d)
    db.close()
    return jsonify(result)


@app.route("/api/items", methods=["POST"])
@login_required
def add_item():
    uid       = current_user_id()
    data      = request.get_json()
    name      = data.get("name", "").strip()
    item_type = data.get("type", "task")
    if not name: return jsonify({"error": "Name required"}), 400
    if item_type not in ("habit", "task"): return jsonify({"error": "Invalid type"}), 400
    db  = get_db()
    cur = db.execute(
        "INSERT INTO items (user_id, name, type, created_at) VALUES (?,?,?,?)",
        (uid, name, item_type, datetime.now().isoformat())
    )
    db.commit()
    item_id = cur.lastrowid
    if item_type == "habit":
        db.execute(
            "INSERT OR IGNORE INTO daily_logs (item_id, log_date, completed) VALUES (?,?,0)",
            (item_id, today())
        )
        db.commit()
    item = row_to_dict(db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())
    item["completed_today"] = False
    item["streak"] = 0
    db.close()
    return jsonify(item), 201


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    uid  = current_user_id()
    db   = get_db()
    item = db.execute("SELECT * FROM items WHERE id=? AND user_id=?", (item_id, uid)).fetchone()
    if not item: return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM daily_logs WHERE item_id=?", (item_id,))
    db.execute("DELETE FROM items WHERE id=?", (item_id,))
    db.commit()
    db.close()
    return jsonify({"deleted": item_id})


@app.route("/api/items/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_item(item_id):
    uid  = current_user_id()
    db   = get_db()
    item = row_to_dict(db.execute(
        "SELECT * FROM items WHERE id=? AND user_id=?", (item_id, uid)
    ).fetchone())
    if not item: return jsonify({"error": "Not found"}), 404
    if item["type"] == "habit":
        log = db.execute(
            "SELECT * FROM daily_logs WHERE item_id=? AND log_date=?",
            (item_id, today())
        ).fetchone()
        if log:
            new_val = 0 if log["completed"] else 1
            db.execute(
                "UPDATE daily_logs SET completed=? WHERE item_id=? AND log_date=?",
                (new_val, item_id, today())
            )
        else:
            new_val = 1
            db.execute(
                "INSERT INTO daily_logs (item_id, log_date, completed) VALUES (?,?,1)",
                (item_id, today())
            )
        db.commit()
        _upsert_daily_points(db, uid, today(), "habit", 1 if new_val else -1)
        db.close()
        streak = calculate_streak(get_db(), item_id)
        return jsonify({"completed_today": bool(new_val), "streak": streak})
    else:
        new_val = 0 if item["completed"] else 1
        db.execute("UPDATE items SET completed=? WHERE id=?", (new_val, item_id))
        db.commit()
        _upsert_daily_points(db, uid, today(), "task", 1 if new_val else -1)
        db.close()
        return jsonify({"completed_today": bool(new_val), "streak": 0})


def _upsert_daily_points(db, user_id, log_date, point_type, delta):
    col      = "habit_points" if point_type == "habit" else "task_points"
    existing = db.execute(
        "SELECT * FROM daily_points WHERE user_id=? AND log_date=?", (user_id, log_date)
    ).fetchone()
    if existing:
        new_val = max(0, existing[col] + delta)
        db.execute(f"UPDATE daily_points SET {col}=? WHERE user_id=? AND log_date=?",
                   (new_val, user_id, log_date))
    else:
        hp = max(0, delta) if point_type == "habit" else 0
        tp = max(0, delta) if point_type == "task"  else 0
        db.execute(
            "INSERT INTO daily_points (user_id, log_date, habit_points, task_points) VALUES (?,?,?,?)",
            (user_id, log_date, hp, tp)
        )
    db.commit()


def calculate_streak(db, item_id):
    logs       = db.execute(
        "SELECT log_date, completed FROM daily_logs WHERE item_id=? ORDER BY log_date DESC",
        (item_id,)
    ).fetchall()
    streak     = 0
    check_date = date.today()
    for log in logs:
        ld = date.fromisoformat(log["log_date"])
        if ld == check_date and log["completed"]:
            streak     += 1
            check_date -= timedelta(days=1)
        else:
            break
    return streak


@app.route("/api/stats")
@login_required
def get_stats():
    uid  = current_user_id()
    days = int(request.args.get("days", 7))
    db   = get_db()
    rows = db.execute(
        "SELECT log_date, habit_points, task_points FROM daily_points "
        "WHERE user_id=? ORDER BY log_date DESC LIMIT ?", (uid, days)
    ).fetchall()
    db.close()
    return jsonify([row_to_dict(r) for r in reversed(rows)])


@app.route("/api/today-summary")
@login_required
def today_summary():
    uid = current_user_id()
    db  = get_db()
    row = db.execute(
        "SELECT habit_points, task_points FROM daily_points WHERE user_id=? AND log_date=?",
        (uid, today())
    ).fetchone()
    db.close()
    if row: return jsonify({"habit_points": row["habit_points"], "task_points": row["task_points"]})
    return jsonify({"habit_points": 0, "task_points": 0})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🚀  Momentum is running → http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
