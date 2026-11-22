"""The rules for events."""
from datetime import date

from database import repository
from database.connection import session
from services.base import RecordService
from utils.validators import (
    ValidationError, clean_date, clean_record_id,
)


class EventService(RecordService):
    """Add, find, change and remove events."""

    KIND = "event"
    FIELDS = (
        ("name", "Event name", True),
        ("event_date", "Date (YYYY-MM-DD)", True),
        ("location", "Location", True),
        ("tradition_id", "Related tradition ID", False),
        ("description", "Description", False),
    )

    def validate_field(self, field, value):
        if field == "name":
            return self._text(value, "Event name", 100)
        if field == "event_date":
            return clean_date(value, "The date")
        if field == "location":
            return self._text(value, "Location", 100)
        if field == "tradition_id":
            return self._clean_tradition_id(value)
        if field == "description":
            return self._text(value, "Description", 500, required=False)
        raise ValueError("Unknown field: {!r}".format(field))

    def _clean_tradition_id(self, value):
        """Return None if empty, else the ID of an existing tradition."""
        if value is None or str(value).strip() == "":
            return None
        tradition_id = clean_record_id(value, "The tradition ID")
        with session(self._conn) as db:
            found = repository.get_record(db, "tradition", tradition_id)
        if found is None:
            raise ValidationError(
                "There is no tradition with ID {}.".format(tradition_id))
        return tradition_id

    def summary(self, today=None):
        """Numbers for the report: all events and the upcoming ones."""
        today = (today or date.today()).isoformat()
        with session(self._conn) as db:
            return {
                "total": repository.count_records(db, self.KIND),
                "upcoming": repository.count_records(
                    db, self.KIND, upcoming_from=today),
            }
