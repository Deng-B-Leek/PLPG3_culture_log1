"""Tests for the menu, using fake keystrokes."""
import unittest
from unittest import mock

from database.connection import DatabaseError, connect
from database.schema import init_db
from services.auth_service import AuthService
from services.event_service import EventService
from services.tradition_service import TraditionService
from ui.menus import Menu

TRADITION = {"name": "Intore dance", "region": "Rwanda",
             "category": "dance", "description": "A warrior dance."}


class Session:
    """Pretends to be the keyboard and the screen."""

    def __init__(self, inputs, ending=EOFError):
        self.inputs = list(inputs)
        self.ending = ending
        self.prompts = []
        self.lines = []

    def input(self, prompt=""):
        self.prompts.append(prompt)
        if not self.inputs:
            raise self.ending       # like pressing Ctrl+D or Ctrl+C
        return self.inputs.pop(0)

    def print(self, *args):
        self.lines.append(" ".join(str(a) for a in args))

    @property
    def text(self):
        return "\n".join(self.lines)


class MenuTestCase(unittest.TestCase):
    # keystrokes for the welcome screen
    ORGANIZER = ["1", "deng", "password123"]
    VOLUNTEER = ["1", "amina", "secret123"]

    def setUp(self):
        self.conn = connect(":memory:")
        init_db(self.conn)
        self.auth = AuthService(self.conn)
        self.auth.create_first_organizer("deng", "password123")
        self.auth.register("amina", "secret123")
        self.traditions = TraditionService(self.conn)
        self.events = EventService(self.conn)
        # one tradition to work with
        organizer = TraditionService(self.conn, role="organizer")
        self.tid = organizer.create(TRADITION)

    def tearDown(self):
        self.conn.close()

    def run_menu(self, inputs, ending=EOFError):
        session = Session(inputs, ending)
        menu = Menu(self.traditions, self.events, self.auth,
                    session.input, session.print)
        menu.run()
        return session, menu


class TestStartAndExit(MenuTestCase):
    def test_exit_from_the_welcome_screen(self):
        session, menu = self.run_menu(["0"])
        self.assertIn("Goodbye", session.text)
        self.assertNotIn("MAIN MENU", session.text)
        self.assertIsNone(menu.user)

    def test_login_then_exit(self):
        session, menu = self.run_menu(self.ORGANIZER + ["0"])
        self.assertIn("Logged in as deng (organizer)", session.text)
        self.assertIn("Goodbye", session.text)
        self.assertEqual(self.traditions.role, "organizer")
        self.assertEqual(self.events.role, "organizer")

    def test_end_of_input_and_ctrl_c_exit_politely(self):
        for ending in (EOFError, KeyboardInterrupt):
            session, _ = self.run_menu(self.ORGANIZER, ending)
            self.assertIn("Goodbye", session.text)

    def test_menu_rejects_bad_choices(self):
        session, _ = self.run_menu(
            self.ORGANIZER + ["abc", "", "9", "-1", "0"])
        self.assertEqual(session.text.count("Please type a whole number"), 2)
        self.assertEqual(session.text.count("Please choose a number"), 2)

    def test_database_problems_do_not_crash_the_menu(self):
        with mock.patch.object(self.traditions, "list_all",
                               side_effect=DatabaseError("disk full")):
            session, _ = self.run_menu(self.ORGANIZER + ["1", "1", "0"])
        self.assertIn("Database problem: disk full", session.text)
        self.assertIn("Goodbye", session.text)


class TestFirstRunAndAccounts(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        init_db(self.conn)
        self.auth = AuthService(self.conn)

    def tearDown(self):
        self.conn.close()

    def run_menu(self, inputs):
        session = Session(inputs)
        menu = Menu(TraditionService(self.conn), EventService(self.conn),
                    self.auth, session.input, session.print)
        menu.run()
        return session, menu

    def test_first_run_setup_logs_the_organizer_straight_in(self):
        session, menu = self.run_menu(
            ["deng", "short", "deng", "longpassword", "0"])
        self.assertIn("First-time setup", session.text)
        self.assertEqual(menu.user["role"], "organizer")
        self.assertFalse(self.auth.needs_setup())
        self.assertNotIn("--- WELCOME ---", session.text)   # no second login
        self.assertIn("MAIN MENU", session.text)
        self.assertEqual(session.inputs, [])

    def test_first_run_setup_can_be_skipped(self):
        session, menu = self.run_menu(["", "0"])
        self.assertIn("--- WELCOME ---", session.text)
        self.assertIsNone(menu.user)
        self.assertTrue(self.auth.needs_setup())

    def test_wrong_password_then_correct_one(self):
        self.auth.create_first_organizer("deng", "password123")
        session, menu = self.run_menu(
            ["1", "deng", "wrong", "1", "deng", "password123", "0"])
        self.assertIn("Invalid username or password", session.text)
        self.assertEqual(menu.user["username"], "deng")

    def test_create_a_volunteer_account(self):
        self.auth.create_first_organizer("deng", "password123")
        session, menu = self.run_menu(
            ["2", "ab", "pw", "2", "bella", "password99", "0"])
        self.assertIn("Username must be", session.text)
        self.assertEqual(menu.user, {"username": "bella", "role": "volunteer"})

    def test_log_out_and_switch_user(self):
        self.auth.create_first_organizer("deng", "password123")
        self.auth.register("amina", "secret123")
        session, menu = self.run_menu(
            ["1", "deng", "password123", "7",
             "1", "amina", "secret123", "0"])
        self.assertEqual(menu.user["username"], "amina")
        self.assertEqual(menu.traditions.role, "volunteer")

    def test_log_out_then_exit_from_welcome(self):
        self.auth.create_first_organizer("deng", "password123")
        session, menu = self.run_menu(
            ["1", "deng", "password123", "7", "0"])
        self.assertIn("Goodbye", session.text)


class TestPermissionChecks(MenuTestCase):
    """A role that is not allowed is sent back before any question."""

    def test_volunteer_is_denied_update_and_delete(self):
        session, _ = self.run_menu(self.VOLUNTEER + ["4", "5", "0"])
        self.assertEqual(session.text.count("Permission denied"), 2)
        self.assertIn("cannot update records", session.text)
        self.assertIn("cannot delete records", session.text)
        self.assertIn("Ask an organizer", session.text)
        self.assertNotIn("Which type of record?", session.text)
        self.assertEqual(session.inputs, [])          # nothing left unused

    def test_denied_volunteer_cannot_change_the_data(self):
        self.run_menu(self.VOLUNTEER + ["4", "5", "0"])
        row = TraditionService(self.conn).get(self.tid)
        self.assertEqual(row["name"], "Intore dance")

    def test_volunteer_may_reach_add(self):
        session, _ = self.run_menu(self.VOLUNTEER + ["3", "0", "0"])
        self.assertNotIn("Permission denied", session.text)
        self.assertEqual(session.text.count("Which type of record?"), 1)

    def test_organizer_may_reach_update_and_delete(self):
        session, _ = self.run_menu(self.ORGANIZER + ["4", "0", "5", "0", "0"])
        self.assertNotIn("Permission denied", session.text)
        self.assertEqual(session.text.count("Which type of record?"), 2)


class TestPickRecordType(MenuTestCase):
    def pick(self, inputs):
        session = Session(inputs)
        menu = Menu(self.traditions, self.events, self.auth,
                    session.input, session.print)
        return menu._pick_record_type(), session

    def test_choices(self):
        self.assertEqual(self.pick(["1"])[0], "tradition")
        self.assertEqual(self.pick(["2"])[0], "event")
        self.assertIsNone(self.pick(["0"])[0])

    def test_bad_input_is_asked_again(self):
        kind, session = self.pick(["x", "7", "2"])
        self.assertEqual(kind, "event")
        self.assertEqual(len(session.prompts), 3)


class TestAddUpdateDelete(MenuTestCase):
    def test_add_tradition_with_reprompts(self):
        session, _ = self.run_menu(self.VOLUNTEER + [
            "3", "1",
            "", "Kente weaving",            # an empty name is refused once
            "Ghana",
            "sport", "craft",               # a bad category is refused once
            "Woven cloth",
            "0"])
        self.assertIn("Name cannot be empty", session.text)
        self.assertIn("Category must be one of", session.text)
        self.assertIn("Saved!", session.text)
        found = TraditionService(self.conn).search("kente")
        self.assertEqual(found[0]["created_by"], "amina")

    def test_add_event_with_date_and_tradition_checks(self):
        session, _ = self.run_menu(self.VOLUNTEER + [
            "3", "2", "Showcase",
            "12/12/2026", "2026-12-12",     # a bad date, then a good one
            "Kigali",
            "999", str(self.tid),           # unknown tradition, then real
            "",
            "0"])
        self.assertIn("real date in the format YYYY-MM-DD", session.text)
        self.assertIn("There is no tradition with ID 999", session.text)
        event = EventService(self.conn).list_all()[0]
        self.assertEqual(event["tradition_name"], "Intore dance")

    def test_add_and_back_out(self):
        self.run_menu(self.VOLUNTEER + ["3", "0", "0"])
        self.assertEqual(len(TraditionService(self.conn).list_all()), 1)

    def test_update_keep_change_and_clear(self):
        self.run_menu(self.ORGANIZER + [
            "4", "1", str(self.tid),
            "",                 # name: keep
            "East Africa",      # region: change
            "",                 # category: keep
            "-",                # description: clear
            "0"])
        row = TraditionService(self.conn).get(self.tid)
        self.assertEqual(row["name"], "Intore dance")
        self.assertEqual(row["region"], "East Africa")
        self.assertEqual(row["category"], "dance")
        self.assertEqual(row["description"], "")

    def test_update_with_nothing_changed(self):
        session, _ = self.run_menu(self.ORGANIZER + [
            "4", "1", str(self.tid), "", "", "", "", "0"])
        self.assertIn("Nothing was changed", session.text)

    def test_update_refuses_a_bad_value_then_accepts_a_good_one(self):
        session, _ = self.run_menu(self.ORGANIZER + [
            "4", "1", str(self.tid), "", "", "sport", "music", "", "0"])
        self.assertIn("Category must be one of", session.text)
        row = TraditionService(self.conn).get(self.tid)
        self.assertEqual(row["category"], "music")

    def test_update_unknown_id_and_not_a_number(self):
        session, _ = self.run_menu(self.ORGANIZER + [
            "4", "1", "99", "4", "1", "abc", "4", "1", "", "0"])
        self.assertIn("There is no tradition with ID 99", session.text)
        self.assertIn("must be a whole number", session.text)

    def test_update_when_there_are_no_records(self):
        TraditionService(self.conn, role="organizer").delete(self.tid)
        session, _ = self.run_menu(self.ORGANIZER + ["4", "1", "0"])
        self.assertIn("There are no tradition records yet", session.text)

    def test_delete_needs_confirmation(self):
        session, _ = self.run_menu(self.ORGANIZER + [
            "5", "1", str(self.tid), "no", "0"])
        self.assertIn("Cancelled", session.text)
        self.assertEqual(len(TraditionService(self.conn).list_all()), 1)

    def test_organizer_deletes_after_confirming(self):
        session, _ = self.run_menu(self.ORGANIZER + [
            "5", "1", str(self.tid), "YES", "0"])
        self.assertIn("Deleted tradition", session.text)
        self.assertEqual(TraditionService(self.conn).list_all(), [])


class TestViewSearchReport(MenuTestCase):
    def test_view_list_and_details(self):
        session, _ = self.run_menu(
            self.VOLUNTEER + ["1", "1", str(self.tid), "0"])
        self.assertIn("Intore dance", session.text)
        self.assertIn("TRADITION #1", session.text)
        self.assertIn("A warrior dance.", session.text)

    def test_view_event_shows_the_tradition_name(self):
        EventService(self.conn, role="organizer").create({
            "name": "Showcase", "event_date": "2026-12-12",
            "location": "Kigali", "tradition_id": self.tid})
        session, _ = self.run_menu(self.VOLUNTEER + ["1", "2", "", "0"])
        self.assertIn("2026-12-12", session.text)
        self.assertIn("Intore dance", session.text)

    def test_view_empty_list_and_bad_ids(self):
        session, _ = self.run_menu(self.VOLUNTEER + [
            "1", "2", "1", "1", "x", "1", "1", "42", "0"])
        self.assertIn("No event records found", session.text)
        self.assertIn("must be a whole number", session.text)
        self.assertIn("There is no tradition with ID 42", session.text)

    def test_search(self):
        session, _ = self.run_menu(self.VOLUNTEER + [
            "2", "1", "rwanda", "2", "1", "nothing-matches", "0"])
        self.assertIn("(1 found)", session.text)
        self.assertIn("No tradition records found", session.text)

    def test_empty_search_is_refused(self):
        session, _ = self.run_menu(self.VOLUNTEER + ["2", "1", "   ", "0"])
        self.assertIn("Please type something to search for", session.text)

    def test_report(self):
        session, _ = self.run_menu(self.VOLUNTEER + ["6", "0"])
        self.assertIn("Traditions recorded : 1", session.text)
        self.assertIn("Events recorded     : 0", session.text)
        self.assertIn("dance", session.text)
        self.assertIn("Rwanda", session.text)


if __name__ == "__main__":
    unittest.main()
