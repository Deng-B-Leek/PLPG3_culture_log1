"""Shared logic of the record services (traditions and events)."""
from database import repository
from database.connection import session
from services.errors import NotFoundError, PermissionDenied
from services.permissions import ROLE_PERMISSIONS, can
from utils.validators import ValidationError, clean_record_id, clean_text


class RecordService:
    """Create, read, update and delete one kind of record, for one role.

    Subclasses set KIND and FIELDS and say how each field is validated.
    A service starts as a volunteer (the most limited role); the menu calls
    set_role() once the user has logged in.
    """

    KIND = ""
    # (field name, prompt label, required) for every editable field
    FIELDS = ()

    def __init__(self, conn=None, role="volunteer"):
        self._conn = conn
        self.role = "volunteer"
        self.username = ""
        self.set_role(role)

    # ---------- role and permissions ----------

    def set_role(self, role, username=""):
        """Set who is using the service (a role, and optionally a name)."""
        if role not in ROLE_PERMISSIONS:
            raise ValueError("Unknown role: {!r}".format(role))
        self.role = role
        self.username = username

    def can(self, action):
        return can(self.role, action)

    def _require(self, action):
        if not self.can(action):
            raise PermissionDenied(
                "Your role ({}) is not allowed to {}.".format(
                    self.role, action))

    # ---------- validation ----------

    def validate_field(self, field, value):
        """Return the cleaned value of one field (subclasses implement)."""
        raise NotImplementedError

    def _clean_all(self, data):
        return {name: self.validate_field(name, data.get(name))
                for name, _, _ in self.FIELDS}

    @staticmethod
    def _text(value, label, max_length, required=True):
        return clean_text(value, label, max_length, required)

    # ---------- the operations ----------

    def create(self, data):
        """Add a record and return its new id."""
        self._require("add")
        cleaned = self._clean_all(data)
        with session(self._conn) as db:
            return repository.insert_record(
                db, self.KIND, cleaned, self.username or self.role)

    def get(self, record_id):
        """Return one record, or raise NotFoundError."""
        record_id = clean_record_id(record_id, "The ID")
        with session(self._conn) as db:
            row = repository.get_record(db, self.KIND, record_id)
        if row is None:
            raise NotFoundError(
                "There is no {} with ID {}.".format(self.KIND, record_id))
        return row

    def list_all(self):
        with session(self._conn) as db:
            return repository.list_records(db, self.KIND)

    def search(self, term):
        term = (term or "").strip()
        if not term:
            raise ValidationError("Please type something to search for.")
        with session(self._conn) as db:
            return repository.search_records(db, self.KIND, term)

    def update(self, record_id, changes):
        """Change some fields of a record; fields not in changes are kept."""
        self._require("update")
        current = self.get(record_id)
        merged = {name: current[name] for name, _, _ in self.FIELDS}
        merged.update(changes)
        cleaned = self._clean_all(merged)
        with session(self._conn) as db:
            repository.update_record(db, self.KIND, current["id"], cleaned)
        return cleaned

    def delete(self, record_id):
        self._require("delete")
        current = self.get(record_id)
        with session(self._conn) as db:
            repository.delete_record(db, self.KIND, current["id"])
