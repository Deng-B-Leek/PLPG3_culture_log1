"""Tests for accounts: first-run setup, sign-up and login."""
import unittest

from database.connection import connect
from database.schema import init_db
from services.auth_service import AuthService
from services.errors import AuthError, PermissionDenied
from utils.validators import ValidationError


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        init_db(self.conn)
        self.auth = AuthService(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_first_account_is_the_organizer_and_only_once(self):
        self.assertTrue(self.auth.needs_setup())
        user = self.auth.create_first_organizer("deng", "password123")
        self.assertEqual(user, {"username": "deng", "role": "organizer"})
        self.assertFalse(self.auth.needs_setup())
        with self.assertRaises(PermissionDenied):
            self.auth.create_first_organizer("other", "password123")

    def test_sign_up_creates_a_volunteer(self):
        user = self.auth.register("amina", "secret123")
        self.assertEqual(user["role"], "volunteer")

    def test_sign_up_validation(self):
        for name in ("ab", "has space", "x" * 21, "bad!", "", None):
            with self.assertRaises(ValidationError, msg=repr(name)):
                self.auth.register(name, "secret123")
        for password in ("short", "", None):
            with self.assertRaises(ValidationError, msg=repr(password)):
                self.auth.register("amina", password)

    def test_username_must_be_unique_ignoring_case(self):
        self.auth.register("amina", "secret123")
        with self.assertRaises(ValidationError):
            self.auth.register("AMINA", "other-password")

    def test_login(self):
        self.auth.register("amina", "secret123")
        self.assertEqual(self.auth.login("amina", "secret123")["role"],
                         "volunteer")
        self.assertEqual(self.auth.login("AMINA", "secret123")["username"],
                         "amina")

    def test_login_failures_all_look_the_same(self):
        self.auth.register("amina", "secret123")
        messages = set()
        for details in (("amina", "wrong"), ("ghost", "secret123"),
                        ("", ""), (None, None)):
            with self.assertRaises(AuthError, msg=repr(details)) as caught:
                self.auth.login(*details)
            messages.add(str(caught.exception))
        self.assertEqual(messages, {"Invalid username or password."})

    def test_passwords_are_salted_and_not_stored_as_typed(self):
        self.auth.register("amina", "secret123")
        self.auth.register("bella", "secret123")
        rows = {r["username"]: r for r in
                self.conn.execute("SELECT * FROM users")}
        self.assertNotIn("secret123", rows["amina"]["password_hash"])
        self.assertEqual(len(rows["amina"]["salt"]), 32)
        self.assertNotEqual(rows["amina"]["password_hash"],
                            rows["bella"]["password_hash"])


if __name__ == "__main__":
    unittest.main()
