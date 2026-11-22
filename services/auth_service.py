"""Sign up, login and passwords."""
import hashlib
import hmac
import re
import secrets

from database import repository
from database.connection import session
from services.errors import AuthError, PermissionDenied
from utils.validators import ValidationError

MIN_PASSWORD_LEN = 8
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
_PBKDF2_ROUNDS = 200000


def _hash_password(password, salt_hex):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex),
        _PBKDF2_ROUNDS).hex()


class AuthService:
    """Create accounts and check logins.

    The first account ever made is the organizer. Everyone who signs
    up after that is a volunteer.
    """

    def __init__(self, conn=None):
        self._conn = conn

    def needs_setup(self):
        """True on the first run, when there are no accounts yet."""
        with session(self._conn) as db:
            return repository.count_users(db) == 0

    def _create_user(self, username, password, role):
        username = (username or "").strip()
        if not _USERNAME_RE.match(username):
            raise ValidationError(
                "Username must be 3-20 letters, digits or underscores.")
        if len(password or "") < MIN_PASSWORD_LEN:
            raise ValidationError(
                "Password must be at least {} characters.".format(
                    MIN_PASSWORD_LEN))
        salt = secrets.token_hex(16)
        with session(self._conn) as db:
            if repository.get_user(db, username) is not None:
                raise ValidationError("That username is already taken.")
            repository.add_user(
                db, username, _hash_password(password, salt), salt, role)
        return {"username": username, "role": role}

    def create_first_organizer(self, username, password):
        """Make the first account (an organizer), on a fresh install only."""
        if not self.needs_setup():
            raise PermissionDenied("Setup has already been done.")
        return self._create_user(username, password, "organizer")

    def register(self, username, password):
        """Make a volunteer account."""
        return self._create_user(username, password, "volunteer")

    def login(self, username, password):
        """Return the user (username and role) if the details are right.

        Raises AuthError if they are not.
        """
        with session(self._conn) as db:
            row = repository.get_user(db, (username or "").strip())
        # hash even if the user does not exist, so both failures take as long
        salt = row["salt"] if row else "00" * 16
        candidate = _hash_password(password or "", salt)
        if row is None or not hmac.compare_digest(
                candidate, row["password_hash"]):
            raise AuthError("Invalid username or password.")
        return {"username": row["username"], "role": row["role"]}
