"""
The Recipe Box - backend (Flask + SQLite)

Serves the frontend from ./static and exposes a small JSON API for
user accounts and per-user favorite recipes stored in a SQLite database.
Recipe search data itself still comes from TheMealDB (called from the browser).
"""
import hmac
import os
import re
import secrets
import sqlite3
from datetime import timedelta
from functools import wraps

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "recipebox.db"))

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"), static_url_path="")
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=16 * 1024,
    # Admin page is disabled unless ADMIN_TOKEN is set (16+ characters).
    ADMIN_TOKEN=os.environ.get("ADMIN_TOKEN", ""),
)

# ------------------------------------------------------------------ database
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS favorites (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    meal_id    TEXT NOT NULL,
    name       TEXT NOT NULL,
    thumb      TEXT NOT NULL DEFAULT '',
    category   TEXT NOT NULL DEFAULT '',
    area       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, meal_id)
);
"""


def init_db():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


init_db()

# ------------------------------------------------------------------ helpers
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
MEAL_ID_RE = re.compile(r"^\d{1,12}$")
THUMB_RE = re.compile(r"^https://[^\s\"'<>]{1,480}$")


def error(message, status):
    return jsonify(error=message), status


def json_body():
    """Mutating endpoints require a JSON body (also a basic CSRF safeguard)."""
    if not request.is_json:
        return None
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return error("Please log in first.", 401)
        return fn(*args, **kwargs)

    return wrapper


def start_session(user_id):
    session.clear()
    session["user_id"] = user_id
    session.permanent = True


# ------------------------------------------------------------------ auth API
@app.post("/api/register")
def register():
    data = json_body()
    if data is None:
        return error("Send a JSON body.", 415)
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not USERNAME_RE.match(username):
        return error("Username must be 3-30 characters: letters, numbers, underscore.", 400)
    if not 6 <= len(password) <= 128:
        return error("Password must be 6-128 characters.", 400)
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return error("That username is already taken.", 409)
    start_session(cur.lastrowid)
    return jsonify(username=username), 201


@app.post("/api/login")
def login():
    data = json_body()
    if data is None:
        return error("Send a JSON body.", 415)
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    row = get_db().execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return error("Incorrect username or password.", 401)
    start_session(row["id"])
    return jsonify(username=row["username"])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    uid = session.get("user_id")
    if not uid:
        return jsonify(user=None)
    row = get_db().execute("SELECT username FROM users WHERE id = ?", (uid,)).fetchone()
    if row is None:
        session.clear()
        return jsonify(user=None)
    return jsonify(user={"username": row["username"]})


# ------------------------------------------------------------ favorites API
def favorite_to_dict(row):
    return {
        "id": row["meal_id"],
        "name": row["name"],
        "thumb": row["thumb"],
        "category": row["category"],
        "area": row["area"],
    }


@app.get("/api/favorites")
@login_required
def list_favorites():
    rows = get_db().execute(
        "SELECT * FROM favorites WHERE user_id = ? ORDER BY id ASC", (session["user_id"],)
    ).fetchall()
    return jsonify(favorites=[favorite_to_dict(r) for r in rows])


@app.post("/api/favorites")
@login_required
def add_favorite():
    data = json_body()
    if data is None:
        return error("Send a JSON body.", 415)
    meal_id = str(data.get("id", ""))
    name = str(data.get("name", "")).strip()
    thumb = str(data.get("thumb", "") or "")
    category = str(data.get("category", "") or "").strip()[:80]
    area = str(data.get("area", "") or "").strip()[:80]
    if not MEAL_ID_RE.match(meal_id):
        return error("Invalid recipe id.", 400)
    if not 1 <= len(name) <= 200:
        return error("Recipe name is required (max 200 characters).", 400)
    if thumb and not THUMB_RE.match(thumb):
        return error("Invalid image URL.", 400)
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO favorites (user_id, meal_id, name, thumb, category, area) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session["user_id"], meal_id, name, thumb, category, area),
    )
    db.commit()
    return jsonify(ok=True), 201


@app.delete("/api/favorites/<meal_id>")
@login_required
def remove_favorite(meal_id):
    db = get_db()
    db.execute(
        "DELETE FROM favorites WHERE user_id = ? AND meal_id = ?", (session["user_id"], meal_id)
    )
    db.commit()
    return jsonify(ok=True)


# ------------------------------------------------------------------ admin API
def admin_enabled():
    return len(app.config.get("ADMIN_TOKEN") or "") >= 16


def admin_required(fn):
    """Admin routes need the secret token in the X-Admin-Token header."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not admin_enabled():
            return error("Not found.", 404)  # hide the feature entirely when not configured
        supplied = request.headers.get("X-Admin-Token", "")
        if not hmac.compare_digest(supplied.encode(), app.config["ADMIN_TOKEN"].encode()):
            return error("Invalid admin token.", 401)
        return fn(*args, **kwargs)

    return wrapper


@app.get("/api/admin/users")
@admin_required
def admin_users():
    db = get_db()
    users = db.execute(
        "SELECT u.id, u.username, u.created_at, COUNT(f.id) AS favorites_count "
        "FROM users u LEFT JOIN favorites f ON f.user_id = u.id "
        "GROUP BY u.id ORDER BY u.id"
    ).fetchall()
    favs = {}
    for row in db.execute("SELECT user_id, name FROM favorites ORDER BY id"):
        favs.setdefault(row["user_id"], []).append(row["name"])
    payload = [
        {
            "id": u["id"],
            "username": u["username"],
            "created_at": u["created_at"],
            "favorites_count": u["favorites_count"],
            "favorites": favs.get(u["id"], []),
        }
        for u in users
    ]
    total_favs = db.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
    resp = jsonify(total_users=len(payload), total_favorites=total_favs, users=payload)
    resp.headers["Cache-Control"] = "no-store"
    return resp  # password hashes are never included


@app.get("/api/health")
def health():
    return jsonify(status="ok")


# ------------------------------------------------------------------ frontend
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/admin")
def admin_page():
    if not admin_enabled():
        return "Page not found", 404
    return send_from_directory(app.static_folder, "admin.html")


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return error("Not found.", 404)
    return "Page not found", 404


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return resp


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
