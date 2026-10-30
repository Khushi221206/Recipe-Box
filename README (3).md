# The Recipe Box — Full-Stack Edition 🍲

**Live demo:** https://recipe-box-msao.onrender.com

Search recipes by dish or ingredient (TheMealDB), and save favorites to **your own account** so they follow you across devices.

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, vanilla JavaScript (`static/`) |
| Backend | Python 3 + Flask (`app.py`), REST/JSON API |
| Database | PostgreSQL in production via [Neon](https://neon.tech) (persistent) · SQLite fallback for local dev (`recipebox.db`, created automatically) |
| External data | TheMealDB public API (called from the browser) |

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 — the same server serves the pages and the API.
No `DATABASE_URL` is set locally, so the app automatically uses the SQLite file.

Run the automated API tests: `python test_app.py`

## API

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/register` | Create account `{username, password}` | – |
| POST | `/api/login` | Log in | – |
| POST | `/api/logout` | Log out | – |
| GET | `/api/me` | Current user (or `null`) | – |
| GET | `/api/favorites` | List my favorites | ✔ |
| POST | `/api/favorites` | Save a favorite `{id, name, thumb, category, area}` | ✔ |
| DELETE | `/api/favorites/<meal_id>` | Remove a favorite | ✔ |
| GET | `/api/health` | Health check — also reports which database is active | – |
| GET | `/api/admin/users` | List all users + their favorites (requires `X-Admin-Token` header) | admin token |

## Database schema

- `users(id, username, password_hash, created_at)` — case-insensitive uniqueness on `username` via `CREATE UNIQUE INDEX ON users (lower(username))`
- `favorites(id, user_id → users.id, meal_id, name, thumb, category, area, created_at, UNIQUE(user_id, meal_id))`

See `schema.sql` (SQLite dialect) and `schema_postgres.sql` (PostgreSQL dialect) for the full reference DDL.
`app.py` creates these tables itself on startup for whichever backend is active — these files are for documentation only.

## Deploy (Render for the app, Neon for the database)

GitHub Pages cannot run a backend, so deploy this folder as a Python web service, with a
real database attached so data survives restarts and redeploys:

1. Push this folder to a GitHub repository (frontend files must be inside `static/`).
2. On [neon.tech](https://neon.tech): create a free project, then copy its connection string
   (`postgresql://user:password@host/dbname?sslmode=require`).
3. On render.com: **New → Web Service** → connect the repo.
4. Build command: `pip install -r requirements.txt` · Start command: `gunicorn app:app`
5. Environment variables:
   - `DATABASE_URL` = the Neon connection string from step 2 (switches the app to PostgreSQL automatically)
   - `SECRET_KEY` = any long random string
   - `COOKIE_SECURE` = `1`
   - `ADMIN_TOKEN` = a secret of your choice, to unlock `/admin.html`

Without `DATABASE_URL`, the app still works but falls back to SQLite, which Render's free plan
resets on every restart/redeploy — fine for a quick demo, not for keeping real data.

## Security notes

- Passwords are stored only as salted hashes (Werkzeug), never in plain text.
- All SQL uses parameterized queries on both backends (no string-built SQL).
- Session cookie is `HttpOnly`, `SameSite=Lax` (and `Secure` when `COOKIE_SECURE=1`).
- Favorites are scoped to the logged-in user on every query.
- The admin endpoint is disabled unless `ADMIN_TOKEN` is explicitly set, and compares tokens using a constant-time comparison.
- Without a backend (e.g. GitHub Pages) the app automatically falls back to browser-only favorites.
