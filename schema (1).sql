-- The Recipe Box database schema (SQLite dialect)
-- app.py creates these tables automatically on first start; this file is for reference/reports.
-- See schema_postgres.sql for the PostgreSQL equivalent used in production on Render.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Case-insensitive uniqueness ("Khushi" and "khushi" are the same account),
-- enforced identically on both SQLite and PostgreSQL via an expression index
-- rather than a backend-specific collation.
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
