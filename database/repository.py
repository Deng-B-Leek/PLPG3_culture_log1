"""All the SQL of the app is in this file.

Every query uses ? placeholders. The column names come from the
lists below, never from what the user types. The commit is done by
session() in database/connection.py.
"""

KINDS = ("tradition", "event")

_TABLE = {"tradition": "traditions", "event": "events"}

EDITABLE_FIELDS = {
    "tradition": ("name", "region", "category", "description"),
    "event": ("name", "event_date", "location", "tradition_id", "description"),
}

_SEARCH_COLUMNS = {
    "tradition": ("name", "region", "category", "description"),
    "event": ("e.name", "e.location", "e.description", "t.name"),
}

_GROUPABLE = {"tradition": ("category", "region"), "event": ()}

_EVENT_SELECT = (
    "SELECT e.*, t.name AS tradition_name FROM events e "
    "LEFT JOIN traditions t ON t.id = e.tradition_id"
)


def _escape_like(term):
    """Make % and _ count as normal characters in a search."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def insert_record(db, kind, values, created_by=""):
    """Add a record and return its id."""
    columns = EDITABLE_FIELDS[kind] + ("created_by",)
    params = [values.get(c) for c in EDITABLE_FIELDS[kind]] + [created_by]
    sql = "INSERT INTO {} ({}) VALUES ({})".format(
        _TABLE[kind], ", ".join(columns), ", ".join("?" * len(columns)))
    return db.execute(sql, params).lastrowid


def get_record(db, kind, record_id):
    """Return one record, or None if it is not there."""
    if kind == "event":
        sql = _EVENT_SELECT + " WHERE e.id = ?"
    else:
        sql = "SELECT * FROM traditions WHERE id = ?"
    return db.execute(sql, (record_id,)).fetchone()


def list_records(db, kind):
    """Return all records (traditions by name, events by date)."""
    if kind == "event":
        sql = (_EVENT_SELECT +
               " ORDER BY e.event_date, e.name COLLATE NOCASE")
    else:
        sql = "SELECT * FROM traditions ORDER BY name COLLATE NOCASE"
    return db.execute(sql).fetchall()


def search_records(db, kind, term):
    """Return the records that have the text in any of their fields."""
    pattern = "%" + _escape_like(term) + "%"
    columns = _SEARCH_COLUMNS[kind]
    where = " OR ".join("{} LIKE ? ESCAPE '\\'".format(c) for c in columns)
    if kind == "event":
        sql = (_EVENT_SELECT + " WHERE " + where +
               " ORDER BY e.event_date, e.name COLLATE NOCASE")
    else:
        sql = ("SELECT * FROM traditions WHERE " + where +
               " ORDER BY name COLLATE NOCASE")
    return db.execute(sql, [pattern] * len(columns)).fetchall()


def update_record(db, kind, record_id, values):
    """Update the fields in values. Return True if something changed."""
    fields = [f for f in EDITABLE_FIELDS[kind] if f in values]
    if not fields:
        return False
    sql = "UPDATE {} SET {} WHERE id = ?".format(
        _TABLE[kind], ", ".join("{} = ?".format(f) for f in fields))
    params = [values[f] for f in fields] + [record_id]
    return db.execute(sql, params).rowcount > 0


def delete_record(db, kind, record_id):
    """Delete a record. Return True if it existed."""
    sql = "DELETE FROM {} WHERE id = ?".format(_TABLE[kind])
    return db.execute(sql, (record_id,)).rowcount > 0


def count_records(db, kind, upcoming_from=None):
    """Count records. upcoming_from only counts events from that date on."""
    sql = "SELECT COUNT(*) FROM {}".format(_TABLE[kind])
    params = ()
    if kind == "event" and upcoming_from is not None:
        sql += " WHERE event_date >= ?"
        params = (upcoming_from,)
    return db.execute(sql, params).fetchone()[0]


def count_by(db, kind, column):
    """Count records grouped by a column, like [(value, count), ...]."""
    if column not in _GROUPABLE[kind]:
        raise ValueError(
            "Cannot group {} records by {}".format(kind, column))
    sql = ("SELECT {c}, COUNT(*) AS n FROM {t} GROUP BY {c} "
           "ORDER BY n DESC, {c} COLLATE NOCASE").format(
               c=column, t=_TABLE[kind])
    return [(row[0], row[1]) for row in db.execute(sql)]


def add_user(db, username, password_hash, salt, role):
    """Add a user and return the id."""
    sql = ("INSERT INTO users (username, password_hash, salt, role) "
           "VALUES (?, ?, ?, ?)")
    return db.execute(sql, (username, password_hash, salt, role)).lastrowid


def get_user(db, username):
    """Return the user (the name is not case sensitive), or None."""
    return db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def count_users(db):
    return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
