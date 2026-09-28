-- The Recipe Box database schema (SQLite)
-- app.py creates these tables automatically on first start; this file is for reference/reports.

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
