"""Tests for the validators, the services and the database layer.

Run from the project root:  python -m unittest discover -v

Every test that needs a database builds its own in-memory one, so the tests
never touch heritage.db and never affect each other.

Owner: Esther (testing)
"""
import unittest
from datetime import date

from database import repository
from database.connection import DatabaseError, connect, session
from database.schema import init_db
from services.errors import NotFoundError, PermissionDenied
from services.event_service import EventService
from services.tradition_service import TraditionService
from utils.validators import (
    ValidationError, clean_choice, clean_date, clean_record_id, clean_text,
)

TRADITION = {"name": "Intore dance", "region": "Rwanda",
             "category": "dance", "description": "A warrior dance."}


class ValidatorTests(unittest.TestCase):
    """clean_text, clean_date, clean_record_id and clean_choice."""

    # ----- clean_text -----

    def test_clean_text_trims_spaces(self):
        self.assertEqual(clean_text("  Kente  ", "Name", 50), "Kente")

    def test_clean_text_rejects_empty_when_required(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                clean_text(bad, "Name", 50)

    def test_clean_text_allows_empty_when_optional(self):
        self.assertEqual(clean_text("", "Note", 50, required=False), "")
        self.assertEqual(clean_text(None, "Note", 50, required=False), "")

    def test_clean_text_checks_the_length_after_trimming(self):
        self.assertEqual(clean_text(" " + "a" * 10 + " ", "N", 10), "a" * 10)
        with self.assertRaises(ValidationError):
            clean_text("a" * 11, "N", 10)

    def test_clean_text_error_names_the_field(self):
        with self.assertRaises(ValidationError) as caught:
            clean_text("", "Region", 50)
        self.assertIn("Region", str(caught.exception))

    # ----- clean_date -----

    def test_clean_date_accepts_real_dates(self):
        self.assertEqual(clean_date("2026-08-07"), "2026-08-07")
        self.assertEqual(clean_date(" 2028-02-29 "), "2028-02-29")  # leap

    def test_clean_date_zero_pads(self):
        self.assertEqual(clean_date("2026-8-7"), "2026-08-07")

    def test_clean_date_rejects_bad_dates(self):
        bad_dates = ("07/08/2026", "2026/08/07", "2026-13-01", "2026-02-30",
                     "2027-02-29", "2026-00-10", "tomorrow", "20260807",
                     "2026-08", "2026-08-07 10:00")
        for bad in bad_dates:
            with self.assertRaises(ValidationError, msg=bad):
                clean_date(bad)

    def test_clean_date_rejects_empty(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                clean_date(bad)

    # ----- clean_record_id -----

    def test_clean_record_id_accepts_whole_numbers(self):
        self.assertEqual(clean_record_id("7"), 7)
        self.assertEqual(clean_record_id(" 12 "), 12)
        self.assertEqual(clean_record_id(3), 3)

    def test_clean_record_id_rejects_invalid_input(self):
        for bad in ("", "  ", "abc", "1.5", "-1", "0", "1e3", "12abc",
                    None, 0, -4, 2.5, True, False, [1], "٣", "1" * 25):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                clean_record_id(bad)

    # ----- clean_choice -----

    def test_clean_choice(self):
        choices = ("dance", "music")
        self.assertEqual(clean_choice(" DANCE ", choices), "dance")
        for bad in ("", None, "sport", "dance music"):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                clean_choice(bad, choices)


class ServiceTests(unittest.TestCase):
    """TraditionService, with one organizer and one volunteer."""

    def setUp(self):
        self.conn = connect(":memory:")
        init_db(self.conn)
        self.organizer = TraditionService(self.conn, role="organizer")
        self.volunteer = TraditionService(self.conn, role="volunteer")

    def tearDown(self):
        self.conn.close()

    def make(self, service=None, **overrides):
        service = service or self.organizer
        return service.create(dict(TRADITION, **overrides))

    # ----- create -----

    def test_organizer_creates_and_reads_a_tradition(self):
        record_id = self.make()
        row = self.organizer.get(record_id)
        self.assertEqual(row["name"], "Intore dance")
        self.assertEqual(row["region"], "Rwanda")
        self.assertEqual(row["category"], "dance")

    def test_volunteer_may_create_and_everyone_sees_it(self):
        record_id = self.make(self.volunteer, name="Kente weaving")
        self.assertEqual(self.organizer.get(record_id)["name"],
                         "Kente weaving")
        self.assertEqual(self.organizer.get(record_id)["created_by"],
                         "volunteer")

    def test_create_cleans_the_values(self):
        record_id = self.make(name="  Kente  ", category="CRAFT")
        row = self.organizer.get(record_id)
        self.assertEqual(row["name"], "Kente")
        self.assertEqual(row["category"], "craft")

    def test_create_rejects_missing_required_fields(self):
        for field in ("name", "region", "category"):
            with self.assertRaises(ValidationError, msg=field):
                self.make(**{field: "  "})
        self.assertEqual(self.organizer.list_all(), [])

    def test_create_rejects_unknown_category_and_long_text(self):
        with self.assertRaises(ValidationError):
            self.make(category="sport")
        with self.assertRaises(ValidationError):
            self.make(name="x" * 101)
        with self.assertRaises(ValidationError):
            self.make(description="x" * 501)

    def test_optional_description_may_be_left_out(self):
        record_id = self.organizer.create(
            {"name": "A", "region": "B", "category": "other"})
        self.assertEqual(self.organizer.get(record_id)["description"], "")

    # ----- list and search -----

    def names(self, term):
        return [r["name"] for r in self.organizer.search(term)]

    def test_list_is_sorted_by_name(self):
        self.make(name="Zulu dance")
        self.make(name="Adowa")
        self.make(name="kente")
        self.assertEqual([r["name"] for r in self.organizer.list_all()],
                         ["Adowa", "kente", "Zulu dance"])

    def test_search_finds_text_in_any_field_in_any_case(self):
        self.make()
        self.make(name="Kente weaving", region="Ghana", category="craft",
                  description="Woven cloth.")
        self.assertEqual(self.names("RWANDA"), ["Intore dance"])
        self.assertEqual(self.names("woven"), ["Kente weaving"])
        self.assertEqual(self.names("craft"), ["Kente weaving"])
        self.assertEqual(self.names("nothing-like-this"), [])

    def test_search_treats_wildcards_as_plain_characters(self):
        self.make()
        self.make(name="50% off day", region="Test_land", category="other")
        self.assertEqual(self.names("%"), ["50% off day"])
        self.assertEqual(self.names("_"), ["50% off day"])

    def test_search_is_safe_against_sql_injection(self):
        self.make()
        self.assertEqual(self.names("'; DROP TABLE traditions; --"), [])
        self.assertEqual(len(self.organizer.list_all()), 1)

    def test_search_rejects_an_empty_term(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                self.organizer.search(bad)

    # ----- update -----

    def test_update_changes_only_the_given_fields(self):
        record_id = self.make()
        self.organizer.update(record_id, {"region": "East Africa"})
        row = self.organizer.get(record_id)
        self.assertEqual(row["region"], "East Africa")
        self.assertEqual(row["name"], "Intore dance")
        self.assertEqual(row["category"], "dance")

    def test_update_can_clear_an_optional_field(self):
        record_id = self.make()
        self.organizer.update(record_id, {"description": ""})
        self.assertEqual(self.organizer.get(record_id)["description"], "")

    def test_update_with_bad_data_changes_nothing(self):
        record_id = self.make()
        with self.assertRaises(ValidationError):
            self.organizer.update(record_id, {"category": "sport"})
        with self.assertRaises(ValidationError):
            self.organizer.update(record_id, {"name": ""})
        row = self.organizer.get(record_id)
        self.assertEqual(row["category"], "dance")
        self.assertEqual(row["name"], "Intore dance")

    # ----- delete -----

    def test_organizer_deletes_a_tradition(self):
        record_id = self.make()
        self.organizer.delete(record_id)
        with self.assertRaises(NotFoundError):
            self.organizer.get(record_id)
        self.assertEqual(self.organizer.list_all(), [])

    def test_delete_leaves_other_records_alone(self):
        keep = self.make(name="Keep me")
        gone = self.make(name="Delete me")
        self.organizer.delete(gone)
        self.assertEqual([r["id"] for r in self.organizer.list_all()], [keep])

    # ----- missing records -----

    def test_missing_records(self):
        with self.assertRaises(NotFoundError):
            self.organizer.get(99)
        with self.assertRaises(NotFoundError):
            self.organizer.update(99, {"name": "X"})
        with self.assertRaises(NotFoundError):
            self.organizer.delete(99)

    def test_bad_ids_are_rejected_before_the_database_is_asked(self):
        for bad in ("abc", "", "0", "-3", None):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                self.organizer.get(bad)

    # ----- volunteer permission blocks -----

    def test_volunteer_cannot_update(self):
        record_id = self.make()
        with self.assertRaises(PermissionDenied):
            self.volunteer.update(record_id, {"name": "Hacked"})
        self.assertEqual(self.organizer.get(record_id)["name"],
                         "Intore dance")

    def test_volunteer_cannot_delete(self):
        record_id = self.make()
        with self.assertRaises(PermissionDenied):
            self.volunteer.delete(record_id)
        self.assertEqual(self.organizer.get(record_id)["name"],
                         "Intore dance")

    def test_permission_is_checked_before_the_record_is_looked_up(self):
        # A volunteer gets "not allowed", not "not found", for an unknown ID.
        with self.assertRaises(PermissionDenied):
            self.volunteer.delete(99)
        with self.assertRaises(PermissionDenied):
            self.volunteer.update(99, {"name": "X"})

    def test_volunteer_can_view_and_search(self):
        record_id = self.make()
        self.assertEqual(self.volunteer.get(record_id)["name"],
                         "Intore dance")
        self.assertEqual(len(self.volunteer.list_all()), 1)
        self.assertEqual(len(self.volunteer.search("rwanda")), 1)

    def test_default_role_is_volunteer(self):
        self.assertEqual(TraditionService(self.conn).role, "volunteer")

    def test_unknown_role_is_refused(self):
        with self.assertRaises(ValueError):
            TraditionService(self.conn, role="admin")
        with self.assertRaises(ValueError):
            self.organizer.set_role("")

    def test_set_role_changes_what_is_allowed(self):
        record_id = self.make()
        service = TraditionService(self.conn, role="volunteer")
        with self.assertRaises(PermissionDenied):
            service.delete(record_id)
        service.set_role("organizer", "deng")
        service.delete(record_id)
        self.assertEqual(service.list_all(), [])

    def test_created_by_uses_the_username_when_there_is_one(self):
        service = TraditionService(self.conn)
        service.set_role("volunteer", "amina")
        record_id = service.create(TRADITION)
        self.assertEqual(service.get(record_id)["created_by"], "amina")

    def test_summary_counts(self):
        self.make()
        self.make(name="Kente", region="Ghana", category="craft")
        self.make(name="Adowa", region="Ghana", category="dance")
        report = self.organizer.summary()
        self.assertEqual(report["total"], 3)
        self.assertEqual(dict(report["by_category"]),
                         {"dance": 2, "craft": 1})
        self.assertEqual(dict(report["by_region"]),
                         {"Ghana": 2, "Rwanda": 1})


class EventServiceTests(unittest.TestCase):
    """EventService, with one organizer and one volunteer."""

    def setUp(self):
        self.conn = connect(":memory:")
        init_db(self.conn)
        self.organizer = EventService(self.conn, role="organizer")
        self.volunteer = EventService(self.conn, role="volunteer")
        self.traditions = TraditionService(self.conn, role="organizer")
        self.tradition_id = self.traditions.create(TRADITION)

    def tearDown(self):
        self.conn.close()

    def make(self, service=None, **overrides):
        data = {"name": "Showcase", "event_date": "2026-12-12",
                "location": "Kigali", "tradition_id": self.tradition_id}
        data.update(overrides)
        return (service or self.organizer).create(data)

    def test_create_event_linked_to_a_tradition(self):
        row = self.organizer.get(self.make())
        self.assertEqual(row["tradition_name"], "Intore dance")
        self.assertEqual(row["event_date"], "2026-12-12")

    def test_create_event_without_a_tradition(self):
        for empty in ("", None, "  "):
            row = self.organizer.get(self.make(tradition_id=empty))
            self.assertIsNone(row["tradition_id"])
            self.assertIsNone(row["tradition_name"])

    def test_event_validation(self):
        for bad_date in ("12/12/2026", "2026-02-30", "soon", ""):
            with self.assertRaises(ValidationError, msg=bad_date):
                self.make(event_date=bad_date)
        for bad_id in ("abc", "0", "-1", "999", 2.5):
            with self.assertRaises(ValidationError, msg=repr(bad_id)):
                self.make(tradition_id=bad_id)
        for field in ("name", "location"):
            with self.assertRaises(ValidationError, msg=field):
                self.make(**{field: " "})
        self.assertEqual(self.organizer.list_all(), [])

    def test_events_are_listed_by_date(self):
        self.make(name="Later", event_date="2027-01-01")
        self.make(name="Sooner", event_date="2026-06-01")
        self.assertEqual([r["name"] for r in self.organizer.list_all()],
                         ["Sooner", "Later"])

    def test_search_also_matches_the_tradition_name(self):
        self.make(name="Gala")
        self.assertEqual([r["name"] for r in self.organizer.search("intore")],
                         ["Gala"])
        self.assertEqual(self.organizer.search("zzz"), [])

    def test_update_event_and_unlink_tradition(self):
        event_id = self.make()
        self.organizer.update(event_id, {"location": "Huye",
                                         "tradition_id": ""})
        row = self.organizer.get(event_id)
        self.assertEqual(row["location"], "Huye")
        self.assertIsNone(row["tradition_id"])
        self.assertEqual(row["name"], "Showcase")

    def test_delete_event_and_missing_event(self):
        event_id = self.make()
        self.organizer.delete(event_id)
        with self.assertRaises(NotFoundError):
            self.organizer.get(event_id)
        with self.assertRaises(NotFoundError):
            self.organizer.delete(event_id)

    def test_deleting_a_tradition_keeps_its_events(self):
        event_id = self.make()
        self.traditions.delete(self.tradition_id)
        row = self.organizer.get(event_id)
        self.assertIsNone(row["tradition_id"])
        self.assertEqual(row["name"], "Showcase")

    def test_volunteer_permissions(self):
        event_id = self.make(self.volunteer)          # may add
        self.assertEqual(self.volunteer.get(event_id)["name"], "Showcase")
        with self.assertRaises(PermissionDenied):
            self.volunteer.update(event_id, {"name": "Hacked"})
        with self.assertRaises(PermissionDenied):
            self.volunteer.delete(event_id)
        self.assertEqual(self.organizer.get(event_id)["name"], "Showcase")

    def test_summary_counts_upcoming_events(self):
        self.make(name="Past", event_date="2020-01-01")
        self.make(name="Today", event_date="2026-11-21")
        self.make(name="Future", event_date="2030-01-01")
        report = self.organizer.summary(today=date(2026, 11, 21))
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["upcoming"], 2)


class DatabaseTests(unittest.TestCase):
    def test_init_db_can_run_twice(self):
        conn = connect(":memory:")
        init_db(conn)
        init_db(conn)
        conn.close()

    def test_session_rolls_back_when_something_fails(self):
        conn = connect(":memory:")
        init_db(conn)
        with self.assertRaises(RuntimeError):
            with session(conn) as db:
                repository.insert_record(db, "tradition", TRADITION, "x")
                raise RuntimeError("boom")
        self.assertEqual(repository.count_records(conn, "tradition"), 0)
        conn.close()

    def test_sqlite_errors_become_database_errors(self):
        conn = connect(":memory:")          # no tables created on purpose
        with self.assertRaises(DatabaseError):
            with session(conn) as db:
                db.execute("SELECT * FROM traditions")
        conn.close()

    def test_unopenable_database_gives_a_database_error(self):
        with self.assertRaises(DatabaseError):
            connect("/no/such/folder/heritage.db")

    def test_grouping_only_works_on_whitelisted_columns(self):
        conn = connect(":memory:")
        init_db(conn)
        with self.assertRaises(ValueError):
            repository.count_by(conn, "tradition", "name; DROP TABLE users")
        conn.close()


if __name__ == "__main__":
    unittest.main()
