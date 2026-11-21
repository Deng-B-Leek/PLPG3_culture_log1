"""Database connection helpers (SQLite).

Services never open connections by hand: they use session(), which commits on
success, rolls back on failure and turns SQLite errors into DatabaseError.
"""
import os
import sqlite3
from contextlib import contextmanager


class DatabaseError(Exception):
    """Something went wrong while talking to the database."""


def get_db_path():
    """The database file: HERITAGE_DB if set, otherwise heritage.db."""
    return os.environ.get("HERITAGE_DB", "heritage.db")


def connect(path=None):
    """Open a connection. Use ':memory:' for a throw-away database (tests)."""
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
    """Yield a connection for one unit of work.

    With no conn, a fresh connection is opened and closed afterwards. With a
    conn (for example an in-memory test database) that connection is reused and
    left open.
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
