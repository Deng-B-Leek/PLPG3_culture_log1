"""Rules for traditions."""
from database import repository
from database.connection import session
from services.base import RecordService
from utils.validators import clean_choice

CATEGORIES = ("dance", "music", "cuisine", "ceremony", "craft",
              "oral tradition", "festival", "other")


class TraditionService(RecordService):
    """Create, find, change and remove traditions."""

    KIND = "tradition"
    FIELDS = (
        ("name", "Name", True),
        ("region", "Region or country", True),
        ("category", "Category ({})".format(", ".join(CATEGORIES)), True),
        ("description", "Description", False),
    )

    def validate_field(self, field, value):
        if field == "name":
            return self._text(value, "Name", 100)
        if field == "region":
            return self._text(value, "Region", 60)
        if field == "category":
            return clean_choice(value, CATEGORIES, "Category")
        if field == "description":
            return self._text(value, "Description", 500, required=False)
        raise ValueError("Unknown field: {!r}".format(field))

    def summary(self):
        """Totals for the report: how many, and by category and region."""
        with session(self._conn) as db:
            return {
                "total": repository.count_records(db, self.KIND),
                "by_category": repository.count_by(db, self.KIND, "category"),
                "by_region": repository.count_by(db, self.KIND, "region"),
            }
