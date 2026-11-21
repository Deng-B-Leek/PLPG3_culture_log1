"""All SQL of the application lives here.

Every function takes an open connection and runs parameterised queries. Column
names that end up in SQL text come from the fixed whitelists below, never from
user input. Committing is done by database.connection.session().
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
    """Escape the LIKE wildcards so a search for '50%' means a literal 50%."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------- records (traditions and events) ----------

def insert_record(db, kind, values, created_by=""):
    """Insert a record and return its new id."""
    columns = EDITABLE_FIELDS[kind] + ("created_by",)
    params = [values.get(c) for c in EDITABLE_FIELDS[kind]] + [created_by]
    sql = "INSERT INTO {} ({}) VALUES ({})".format(
        _TABLE[kind], ", ".join(columns), ", ".join("?" * len(columns)))
    return db.execute(sql, params).lastrowid


def get_record(db, kind, record_id):
    """Return one record as a Row, or None if it does not exist."""
    if kind == "event":
        sql = _EVENT_SELECT + " WHERE e.id = ?"
    else:
        sql = "SELECT * FROM traditions WHERE id = ?"
    return db.execute(sql, (record_id,)).fetchone()


def list_records(db, kind):
    """Return all records of a kind (traditions by name, events by date)."""
    if kind == "event":
        sql = (_EVENT_SELECT +
               " ORDER BY e.event_date, e.name COLLATE NOCASE")
    else:
        sql = "SELECT * FROM traditions ORDER BY name COLLATE NOCASE"
    return db.execute(sql).fetchall()


def search_records(db, kind, term):
    """Return the records whose text fields contain term (any case)."""
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
    """Update the given fields. Return True if a record was changed."""
    fields = [f for f in EDITABLE_FIELDS[kind] if f in values]
    if not fields:
        return False
    sql = "UPDATE {} SET {} WHERE id = ?".format(
        _TABLE[kind], ", ".join("{} = ?".format(f) for f in fields))
    params = [values[f] for f in fields] + [record_id]
    return db.execute(sql, params).rowcount > 0


def delete_record(db, kind, record_id):
    """Delete a record. Return True if a record was removed."""
    sql = "DELETE FROM {} WHERE id = ?".format(_TABLE[kind])
    return db.execute(sql, (record_id,)).rowcount > 0


def count_records(db, kind, upcoming_from=None):
    """Count records. For events, upcoming_from limits to date >= value."""
    sql = "SELECT COUNT(*) FROM {}".format(_TABLE[kind])
    params = ()
    if kind == "event" and upcoming_from is not None:
        sql += " WHERE event_date >= ?"
        params = (upcoming_from,)
    return db.execute(sql, params).fetchone()[0]


def count_by(db, kind, column):
    """Return [(value, count), ...] grouped by a whitelisted column."""
    if column not in _GROUPABLE[kind]:
        raise ValueError(
            "Cannot group {} records by {}".format(kind, column))
    sql = ("SELECT {c}, COUNT(*) AS n FROM {t} GROUP BY {c} "
           "ORDER BY n DESC, {c} COLLATE NOCASE").format(
               c=column, t=_TABLE[kind])
    return [(row[0], row[1]) for row in db.execute(sql)]


# ---------- users ----------

def add_user(db, username, password_hash, salt, role):
    """Insert a user and return the new id."""
    sql = ("INSERT INTO users (username, password_hash, salt, role) "
           "VALUES (?, ?, ?, ?)")
    return db.execute(sql, (username, password_hash, salt, role)).lastrowid


def get_user(db, username):
    """Return a user Row (the name match ignores case), or None."""
    return db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def count_users(db):
    return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
