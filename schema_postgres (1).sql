-- The Recipe Box database schema (PostgreSQL dialect)
-- app.py creates these tables automatically on first start when DATABASE_URL
-- is set (e.g. a Render PostgreSQL instance). This file is for reference/reports.

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
