import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_PATH"] = os.path.join(_tmp, "test.db")

import app as recipe_app  # noqa: E402


MEAL = {"id": "52771", "name": "Spicy Arrabiata Penne",
        "thumb": "https://www.themealdb.com/images/media/meals/ustsqw1468250014.jpg",
        "category": "Vegetarian", "area": "Italian"}


class RecipeBoxAPITests(unittest.TestCase):
    def setUp(self):
        self.client = recipe_app.app.test_client()
        with recipe_app.app.app_context():
            db = recipe_app.get_db()
            db.execute("DELETE FROM favorites")
            db.execute("DELETE FROM users")
            db.commit()

    def register(self, client=None, name="khushi", pw="secret123"):
        return (client or self.client).post("/api/register", json={"username": name, "password": pw})

    def test_frontend_is_served(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Recipe Box", r.data)
        self.assertEqual(self.client.get("/script.js").status_code, 200)

    def test_register_login_logout_me(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.client.get("/api/me").get_json()["user"]["username"], "khushi")
        self.client.post("/api/logout")
        self.assertIsNone(self.client.get("/api/me").get_json()["user"])
        self.assertEqual(self.client.post("/api/login", json={"username": "KHUSHI", "password": "secret123"}).status_code, 200)
        self.assertEqual(self.client.get("/api/me").get_json()["user"]["username"], "khushi")

    def test_bad_credentials_and_validation(self):
        self.register()
        c = recipe_app.app.test_client()
        self.assertEqual(c.post("/api/login", json={"username": "khushi", "password": "wrong"}).status_code, 401)
        self.assertEqual(c.post("/api/login", json={"username": "nobody", "password": "x"}).status_code, 401)
        self.assertEqual(self.register(c, "khushi", "another1").status_code, 409)   # duplicate
        self.assertEqual(self.register(c, "ab", "secret123").status_code, 400)       # short name
        self.assertEqual(self.register(c, "bad name!", "secret123").status_code, 400)
        self.assertEqual(self.register(c, "valid_name", "123").status_code, 400)     # short pw
        self.assertEqual(c.post("/api/register", data="x", content_type="text/plain").status_code, 415)

    def test_password_is_hashed(self):
        self.register()
        with recipe_app.app.app_context():
            row = recipe_app.get_db().execute("SELECT password_hash FROM users").fetchone()
        self.assertNotIn("secret123", row["password_hash"])

    def test_favorites_require_login(self):
        self.assertEqual(self.client.get("/api/favorites").status_code, 401)
        self.assertEqual(self.client.post("/api/favorites", json=MEAL).status_code, 401)
        self.assertEqual(self.client.delete("/api/favorites/52771").status_code, 401)

    def test_favorites_add_list_remove_and_persist(self):
        self.register()
        self.assertEqual(self.client.post("/api/favorites", json=MEAL).status_code, 201)
        self.client.post("/api/favorites", json=MEAL)  # duplicate ignored
        favs = self.client.get("/api/favorites").get_json()["favorites"]
        self.assertEqual(favs, [MEAL])
        # survives logout/login (i.e. really stored in the database)
        self.client.post("/api/logout")
        self.client.post("/api/login", json={"username": "khushi", "password": "secret123"})
        self.assertEqual(len(self.client.get("/api/favorites").get_json()["favorites"]), 1)
        self.client.delete("/api/favorites/52771")
        self.assertEqual(self.client.get("/api/favorites").get_json()["favorites"], [])

    def test_favorites_are_private_per_user(self):
        self.register(name="alice")
        self.client.post("/api/favorites", json=MEAL)
        other = recipe_app.app.test_client()
        self.register(other, "bob")
        self.assertEqual(other.get("/api/favorites").get_json()["favorites"], [])
        other.delete("/api/favorites/52771")  # must not touch alice's data
        self.assertEqual(len(self.client.get("/api/favorites").get_json()["favorites"]), 1)

    def test_favorite_validation(self):
        self.register()
        bad = [dict(MEAL, id="abc"), dict(MEAL, id=""), dict(MEAL, name=""),
               dict(MEAL, thumb='https://x.com/a"onerror="alert(1)'), dict(MEAL, thumb="javascript:alert(1)")]
        for payload in bad:
            self.assertEqual(self.client.post("/api/favorites", json=payload).status_code, 400, payload)

    def test_sql_injection_attempt_is_harmless(self):
        self.register()
        r = self.client.post("/api/login", json={"username": "' OR '1'='1", "password": "' OR '1'='1"})
        self.assertEqual(r.status_code, 401)

    def test_unknown_api_route_is_json_404(self):
        r = self.client.get("/api/nope")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.get_json())


if __name__ == "__main__":
    unittest.main(verbosity=2)
