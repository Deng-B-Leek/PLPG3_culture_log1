"""The database schema and its creation."""
import sqlite3

from database.connection import DatabaseError, connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('organizer', 'volunteer'))
);

CREATE TABLE IF NOT EXISTS traditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    event_date TEXT NOT NULL,
    location TEXT NOT NULL,
    tradition_id INTEGER REFERENCES traditions (id) ON DELETE SET NULL,
    description TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(conn=None):
    """Create the tables if they do not exist yet. Safe to call every start."""
    own = conn is None
    db = connect() if own else conn
    try:
        db.executescript(SCHEMA)
        db.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(
            "Could not create the tables: {}".format(exc)) from exc
    finally:
        if own:
            db.close()
