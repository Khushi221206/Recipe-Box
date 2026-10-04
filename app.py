"""
The Recipe Box - backend (Flask + PostgreSQL, with SQLite fallback)

Serves the frontend from ./static and exposes a small JSON API for
user accounts and per-user favorite recipes.

Database backend is chosen automatically:
  - If a DATABASE_URL environment variable is set (Render Postgres provides
    one automatically once a database is attached), PostgreSQL is used and
    data persists across deploys/restarts.
  - Otherwise the app falls back to a local SQLite file, which is enough
    for local development but is reset on Render's free plan.

Recipe search data itself still comes from TheMealDB (called from the browser).
"""
import os
import re
import secrets
from datetime import timedelta
from functools import wraps

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------ database setup
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    # Some hosts (including Render) hand out "postgres://"; psycopg2 accepts
    # it, but normalize to "postgresql://" for compatibility with other tools.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    IntegrityError = psycopg2.IntegrityError
else:
    import sqlite3

    DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "recipebox.db"))
    IntegrityError = sqlite3.IntegrityError

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"), static_url_path="")
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=16 * 1024,
)

# Username case-insensitivity is enforced the same way on both backends, via
# a unique index on lower(username), rather than a backend-specific collation.
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx ON users (lower(username));
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

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS')
);
CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx ON users (lower(username));
CREATE TABLE IF NOT EXISTS favorites (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    meal_id    TEXT NOT NULL,
    name       TEXT NOT NULL,
    thumb      TEXT NOT NULL DEFAULT '',
    category   TEXT NOT NULL DEFAULT '',
    area       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'),
    UNIQUE (user_id, meal_id)
);
"""


class Database:
    """Thin wrapper so every route can use the same '?'-style SQL regardless
    of which backend is active. Only two things differ between the two
    drivers: the placeholder character, and how to get a new row's id back
    after an INSERT (SQLite: cursor.lastrowid, Postgres: RETURNING id)."""

    def __init__(self, conn, is_pg):
        self.conn = conn
        self.is_pg = is_pg

    def _sql(self, query):
        return query.replace("?", "%s") if self.is_pg else query

    def execute(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(self._sql(query), params)
        return cur

    def insert(self, query, params=()):
        """Run an INSERT and return the new row's id."""
        if self.is_pg:
            cur = self.execute(query + " RETURNING id", params)
            return cur.fetchone()["id"]
        cur = self.execute(query, params)
        return cur.lastrowid

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def init_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        cur.execute(POSTGRES_SCHEMA)
        conn.commit()
        cur.close()
        conn.close()
    else:
        folder = os.path.dirname(DB_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(SQLITE_SCHEMA)


def get_db():
    if "db" not in g:
        if USE_POSTGRES:
            raw = psycopg2.connect(
                DATABASE_URL, sslmode="require", cursor_factory=psycopg2.extras.RealDictCursor
            )
            g.db = Database(raw, is_pg=True)
        else:
            raw = sqlite3.connect(DB_PATH)
            raw.row_factory = sqlite3.Row
            raw.execute("PRAGMA foreign_keys = ON")
            g.db = Database(raw, is_pg=False)
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
        new_id = db.insert(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return error("That username is already taken.", 409)
    start_session(new_id)
    return jsonify(username=username), 201


@app.post("/api/login")
def login():
    data = json_body()
    if data is None:
        return error("Send a JSON body.", 415)
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    row = get_db().execute(
        "SELECT id, username, password_hash FROM users WHERE lower(username) = lower(?)",
        (username,),
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
    conflict_clause = "ON CONFLICT (user_id, meal_id) DO NOTHING" if db.is_pg else ""
    insert_or_ignore = "INSERT INTO" if db.is_pg else "INSERT OR IGNORE INTO"
    db.execute(
        f"{insert_or_ignore} favorites (user_id, meal_id, name, thumb, category, area) "
        f"VALUES (?, ?, ?, ?, ?, ?) {conflict_clause}",
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


@app.get("/api/health")
def health():
    return jsonify(status="ok", database="postgresql" if USE_POSTGRES else "sqlite")


# ------------------------------------------------------------------ admin API
# Set ADMIN_TOKEN as an environment variable (on Render: Environment tab).
# If it is not set, the admin endpoint stays disabled.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


@app.get("/api/admin/users")
def admin_users():
    token = request.headers.get("X-Admin-Token", "")
    if not ADMIN_TOKEN or not secrets.compare_digest(token.encode(), ADMIN_TOKEN.encode()):
        return error("Forbidden: wrong or missing admin token.", 403)
    db = get_db()
    users = db.execute("SELECT id, username, created_at FROM users ORDER BY id").fetchall()
    favs = db.execute("SELECT user_id, name FROM favorites ORDER BY id").fetchall()
    by_user = {}
    for f in favs:
        by_user.setdefault(f["user_id"], []).append(f["name"])
    out = [
        {
            "id": u["id"],
            "username": u["username"],
            "created_at": u["created_at"],
            "favorites_count": len(by_user.get(u["id"], [])),
            "favorites": by_user.get(u["id"], []),
        }
        for u in users
    ]
    return jsonify(total_users=len(out), total_favorites=len(favs), users=out)


# ------------------------------------------------------------------ frontend
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


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
