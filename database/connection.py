"""Connecting to the SQLite database."""
import os
import sqlite3
from contextlib import contextmanager


class DatabaseError(Exception):
    """Raised when something goes wrong with the database."""


def get_db_path():
    """Return the database file name (heritage.db by default)."""
    return os.environ.get("HERITAGE_DB", "heritage.db")


def connect(path=None):
    """Open the database. Use ':memory:' for tests."""
    path = path or get_db_path()
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.Error as exc:
        raise DatabaseError(
            "Could not open the database '{}': {}".format(path, exc)) from exc
    return conn


@contextmanager
def session(conn=None):
    """Give a connection for one piece of work.

    Commits if it works and rolls back if it fails. If no conn is
    given it opens its own and closes it at the end.
    """
    own = conn is None
    db = connect() if own else conn
    try:
        yield db
        db.commit()
    except sqlite3.Error as exc:
        db.rollback()
        raise DatabaseError(str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    finally:
        if own:
            db.close()
