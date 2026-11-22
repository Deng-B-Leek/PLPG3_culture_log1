"""The menu part of the app: what the user sees and types.

Menu.run() is the main loop. It shows the menu, does what the user
picks, then shows the menu again until they exit. The menu only talks
to the services, never to the database.

Owner: Davina
"""
from database.connection import DatabaseError
from services.errors import (
    AuthError, NotFoundError, PermissionDenied,
)
from services.permissions import ACTION_LABELS, can
from utils.validators import ValidationError

BANNER = """\
==========================================
   COMMUNITY CULTURE AND HERITAGE LOG
   Keep our traditions and events alive
=========================================="""

MAIN_MENU = """
--- MAIN MENU ---
1. View records
2. Search records
3. Add a record
4. Update a record
5. Delete a record
6. Summary report
7. Log out (switch user)
0. Exit"""


class Menu:
    """The command line menu."""

    def __init__(self, traditions, events, auth, input_fn=None,
                 output_fn=print):
        self.traditions = traditions
        self.events = events
        self.auth = auth
        self._input = input_fn or (lambda prompt="": input(prompt))
        self._print = output_fn
        self.user = None  # set after login: username and role

    # the main loop

    def run(self):
        """Show the menu again and again until the user exits."""
        self._print(BANNER)
        try:
            if self._welcome():
                self._main_loop()
        except (EOFError, KeyboardInterrupt):
            self._print("")
        self._print("\nThank you for keeping our heritage alive. Goodbye!")

    def _main_loop(self):
        while True:
            self._show_status()
            self._print(MAIN_MENU)
            choice = self._ask_int("Choose 0-7: ", 0, 7)
            if choice == 0:
                return
            try:
                if choice == 1:
                    self._view_records()
                elif choice == 2:
                    self._search_records()
                elif choice == 3:
                    self._add_record()
                elif choice == 4:
                    self._update_record()
                elif choice == 5:
                    self._delete_record()
                elif choice == 6:
                    self._show_report()
                else:
                    self.user = None
                    if not self._welcome():
                        return
            except DatabaseError as error:
                self._print("\n  Database problem: {}".format(error))
                self._print("  Nothing was lost. Returning to the menu.")

    # choose a tradition or an event

    def _pick_record_type(self):
        """Ask for a tradition or an event (None means the user went back)."""
        self._print("\nWhich type of record?")
        self._print("1. Tradition")
        self._print("2. Event")
        self._print("0. Back")
        choice = self._ask_int("Choose 0-2: ", 0, 2)
        if choice == 1:
            return "tradition"
        if choice == 2:
            return "event"
        return None

    def _service_for(self, kind):
        return self.traditions if kind == "tradition" else self.events

    # welcome screen and login

    def _welcome(self):
        """Log in or sign up.

        Returns True once someone is in, or False if they exit.
        """
        if self.auth.needs_setup():
            self._first_run_setup()
            if self.user is not None:
                return True   # the new organizer is already logged in
        while True:
            self._print("\n--- WELCOME ---")
            self._print("1. Log in")
            self._print("2. Create a volunteer account")
            self._print("0. Exit")
            choice = self._ask_int("Choose 0-2: ", 0, 2)
            if choice == 0:
                return False
            if choice == 1 and self._login():
                return True
            if choice == 2 and self._register():
                return True

    def _first_run_setup(self):
        self._print("\nFirst-time setup: create the organizer account.")
        self._print("The organizer can add, update and delete records.")
        self._print("(Press Enter at the username to skip.)")
        while True:
            username = self._ask("Organizer username: ")
            if username == "":
                return
            password = self._ask("Organizer password (min 8 characters): ")
            try:
                user = self.auth.create_first_organizer(username, password)
            except ValidationError as error:
                self._print("  " + str(error))
                continue
            self._print("  Organizer account created. You are logged in.")
            self._enter(user)
            return

    def _login(self):
        username = self._ask("Username: ")
        password = self._ask("Password: ")
        try:
            user = self.auth.login(username, password)
        except AuthError as error:
            self._print("  " + str(error))
            return False
        self._print("  Welcome back, {}!".format(user["username"]))
        self._enter(user)
        return True

    def _register(self):
        username = self._ask("Choose a username: ")
        password = self._ask("Choose a password (min 8 characters): ")
        try:
            user = self.auth.register(username, password)
        except ValidationError as error:
            self._print("  " + str(error))
            return False
        self._print("  Account created. Welcome, {}!".format(user["username"]))
        self._enter(user)
        return True

    def _enter(self, user):
        """Remember who logged in and give both services their role."""
        self.user = user
        self.traditions.set_role(user["role"], user["username"])
        self.events.set_role(user["role"], user["username"])

    # the actions

    def _view_records(self):
        kind = self._pick_record_type()
        if kind is None:
            return
        service = self._service_for(kind)
        records = service.list_all()
        self._print_table(kind, records)
        if not records:
            return
        raw = self._ask(
            "Type an ID to see its full details (Enter to go back): ")
        if raw == "":
            return
        try:
            self._print_details(kind, service.get(raw))
        except (ValidationError, NotFoundError) as error:
            self._print("  " + str(error))

    def _search_records(self):
        kind = self._pick_record_type()
        if kind is None:
            return
        term = self._ask("Search for: ")
        try:
            records = self._service_for(kind).search(term)
        except ValidationError as error:
            self._print("  " + str(error))
            return
        self._print_table(kind, records)

    def _add_record(self):
        # check the role first, before asking anything
        if not self._allowed("add"):
            return
        kind = self._pick_record_type()
        if kind is None:
            return
        service = self._service_for(kind)
        data = {}
        for field, label, required in service.FIELDS:
            data[field] = self._ask_field(service, field, label, required)
        try:
            new_id = service.create(data)
        except (ValidationError, PermissionDenied) as error:
            self._print("  Could not save: {}".format(error))
            return
        self._print("  Saved! The new {} has ID {}.".format(kind, new_id))

    def _update_record(self):
        # check the role first, before asking anything
        if not self._allowed("update"):
            return
        kind = self._pick_record_type()
        if kind is None:
            return
        service = self._service_for(kind)
        record = self._ask_existing_record(kind, "update")
        if record is None:
            return
        self._print("Press Enter to keep the current value. "
                    "Type - to clear an optional field.")
        changes = {}
        for field, label, required in service.FIELDS:
            current = record[field]
            shown = "" if current is None else current
            while True:
                raw = self._ask("{} [{}]: ".format(
                    label.split(" (")[0], shown))
                if raw == "":
                    break
                if raw == "-" and not required:
                    changes[field] = ""
                    break
                try:
                    changes[field] = service.validate_field(field, raw)
                    break
                except ValidationError as error:
                    self._print("  " + str(error))
        if not changes:
            self._print("  Nothing was changed.")
            return
        try:
            service.update(record["id"], changes)
        except (ValidationError, PermissionDenied, NotFoundError) as error:
            self._print("  Could not update: {}".format(error))
            return
        self._print("  Updated {} {}.".format(kind, record["id"]))

    def _delete_record(self):
        # check the role first, before asking anything
        if not self._allowed("delete"):
            return
        kind = self._pick_record_type()
        if kind is None:
            return
        record = self._ask_existing_record(kind, "delete")
        if record is None:
            return
        answer = self._ask(
            "Delete '{}' for good? Type yes to confirm: ".format(
                record["name"])).lower()
        if answer != "yes":
            self._print("  Cancelled. Nothing was deleted.")
            return
        try:
            self._service_for(kind).delete(record["id"])
        except (PermissionDenied, NotFoundError) as error:
            self._print("  Could not delete: {}".format(error))
            return
        self._print("  Deleted {} {}.".format(kind, record["id"]))

    def _show_report(self):
        traditions = self.traditions.summary()
        events = self.events.summary()
        self._print("\n--- SUMMARY REPORT ---")
        self._print("Traditions recorded : {}".format(traditions["total"]))
        self._print("Events recorded     : {}".format(events["total"]))
        self._print("Upcoming events     : {}".format(events["upcoming"]))
        if traditions["by_category"]:
            self._print("\nTraditions by category:")
            for name, count in traditions["by_category"]:
                self._print("  {:<16} {}".format(name, count))
        if traditions["by_region"]:
            self._print("\nTraditions by region:")
            for name, count in traditions["by_region"]:
                self._print("  {:<16} {}".format(name, count))

    # permission check

    def _allowed(self, action):
        """Check the role. If it is not allowed, say so and return False."""
        if can(self.user["role"], action):
            return True
        self._print("\n  Permission denied: your role ({}) cannot {}.".format(
            self.user["role"], ACTION_LABELS[action]))
        self._print("  Ask an organizer to do this for you.")
        return False

    # input helpers

    def _ask(self, prompt):
        return self._input(prompt).strip()

    def _ask_int(self, prompt, low, high):
        """Ask until the user types a whole number from low to high."""
        while True:
            try:
                value = int(self._ask(prompt))
            except ValueError:
                self._print(
                    "  Please type a whole number from {} to {}.".format(
                        low, high))
                continue
            if low <= value <= high:
                return value
            self._print("  Please choose a number from {} to {}.".format(
                low, high))

    def _ask_field(self, service, field, label, required):
        """Ask for one field until the service accepts it."""
        suffix = "" if required else " (optional, Enter to skip)"
        while True:
            raw = self._ask("{}{}: ".format(label, suffix))
            try:
                return service.validate_field(field, raw)
            except ValidationError as error:
                self._print("  " + str(error))

    def _ask_existing_record(self, kind, verb):
        """Show the records, ask for an ID and return that record (or None)."""
        service = self._service_for(kind)
        records = service.list_all()
        if not records:
            self._print("  There are no {} records yet.".format(kind))
            return None
        self._print_table(kind, records)
        raw = self._ask("ID of the {} to {} (Enter to cancel): ".format(
            kind, verb))
        if raw == "":
            return None
        try:
            return service.get(raw)
        except (ValidationError, NotFoundError) as error:
            self._print("  " + str(error))
            return None

    # output helpers

    def _show_status(self):
        self._print("\nLogged in as {} ({})".format(
            self.user["username"], self.user["role"]))

    def _print_table(self, kind, records):
        if not records:
            self._print("\n  No {} records found.".format(kind))
            return
        if kind == "tradition":
            self._print("\n{:<4} {:<28} {:<18} {}".format(
                "ID", "Name", "Region", "Category"))
            for r in records:
                self._print("{:<4} {:<28} {:<18} {}".format(
                    r["id"], _cut(r["name"], 28), _cut(r["region"], 18),
                    r["category"]))
        else:
            self._print("\n{:<4} {:<11} {:<26} {:<18} {}".format(
                "ID", "Date", "Event", "Location", "Tradition"))
            for r in records:
                self._print("{:<4} {:<11} {:<26} {:<18} {}".format(
                    r["id"], r["event_date"], _cut(r["name"], 26),
                    _cut(r["location"], 18), r["tradition_name"] or "-"))
        self._print("({} found)".format(len(records)))

    def _print_details(self, kind, record):
        service = self._service_for(kind)
        self._print("\n--- {} #{} ---".format(kind.upper(), record["id"]))
        for field, label, _ in service.FIELDS:
            value = record[field]
            if field == "tradition_id":
                label, value = "Related tradition", record["tradition_name"]
            self._print("{:<18}: {}".format(
                label.split(" (")[0], value or "-"))
        self._print("{:<18}: {}".format(
            "Added by", record["created_by"] or "-"))
        self._print("{:<18}: {}".format("Added on", record["created_at"]))


def _cut(text, width):
    """Cut long text so it fits in a table column."""
    text = str(text)
    return text if len(text) <= width else text[:width - 3] + "..."
