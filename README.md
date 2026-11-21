# Community Culture and Heritage Management System

A command-line application for recording and exploring the traditions and
events of a community. It is a menu-driven Python program that keeps its data
in a SQLite database, so nothing is lost when you close it.

**Peer Learning Project 2, Group 3 (African Leadership University, BSE Year 1, Trimester 2)**

## Team

| Member | Role | Files |
|--------|------|-------|
| Deng | Project coordinator: startup, putting the parts together, run instructions | `main.py`, `README.md` |
| Davina | User journey: the menu flow, the decisions and the flowchart | `ui/menus.py`, architecture section of this README |
| Esther | Testing: checks that the code and the permissions work | `tests/` |
| (add name) | Service layer: rules, validation, permissions, accounts | `services/`, `utils/` |
| (add name) | Database layer: schema and SQL | `database/` |

## Run it

You need Python 3.8 or newer. Nothing else has to be installed.

```bash
python main.py
```

On the very first run the app asks you to create the **organizer** account. After
that, people can log in, or create a **volunteer** account from the welcome
screen. The data is saved in `heritage.db` in the folder you run it from. To use
another file, set the `HERITAGE_DB` environment variable:

```bash
HERITAGE_DB=other.db python main.py
```

### Run the tests

```bash
python -m unittest discover -v
```

Run it from the project root. Every test builds its own in-memory database, so
the tests never touch `heritage.db`. A failing test names the exact file and
line.

## What the program does

- Record **traditions** (name, region, category, description) and **events**
  (name, date, location, an optional related tradition, description).
- **View**, **search** (any text, any case), **add**, **update** and **delete**
  records.
- A **summary report**: totals, upcoming events, and traditions by category and
  by region.
- **Accounts with roles**, so that only the right people can change or remove
  records.

### Roles

| Action | Volunteer | Organizer |
|--------|:---------:|:---------:|
| View, search, summary report | yes | yes |
| Add a record | yes | yes |
| Update a record | no | yes |
| Delete a record | no | yes |

The first account ever created is the organizer. Everyone who signs up after
that is a volunteer. If a role is not allowed to do something, the program says
so straight away and returns to the menu, **before asking any questions**.

## Architecture

The program has three layers. Each layer only talks to the one below it, and
`main.py` joins them together.

```
  main.py                 starts the program and joins the layers
     |
     v
  ui/menus.py             MENU layer      what the user sees and types
     |                    (Menu: the menu loop, prompts, tables, permission checks)
     v
  services/               SERVICE layer   the rules of the app
     |                    (TraditionService, EventService, AuthService;
     |                     roles in permissions.py; checks in utils/validators.py)
     v
  database/               DATABASE layer  the only code that touches SQLite
                          (connection.py, schema.py, repository.py)
```

| Layer | Where | Job |
|-------|-------|-----|
| Menu | `ui/menus.py` | The user journey: show the menu, read the choice, call the right service, show the result. No SQL and no business rules. |
| Service | `services/`, `utils/validators.py` | Every rule lives here once: checking each answer, who may do what, passwords, report numbers. |
| Database | `database/` | The tables and all the SQL. It makes no decisions. |

Why three layers? A change stays in one place: a new rule goes in the service, a
new screen goes in the menu. Each layer can also be tested on its own. The
services check permissions themselves too, so the rules hold even if a menu
check were ever missed.

### The user journey

`Menu.run()` in `ui/menus.py` is the central decision point. It shows the main
menu, reads a choice, runs the matching action, and comes back to the menu until
the user chooses to exit.

- `run()` is the menu loop. Each choice leads to exactly one action.
- `_pick_record_type()` is the branch where the user chooses a **tradition** or
  an **event** (or goes back).
- `_add_record()`, `_update_record()` and `_delete_record()` each begin with a
  **permission check** (`_allowed()`). If the role is not allowed, the user is
  sent back to the menu before being asked for any input.
- Ctrl+C and Ctrl+D (end of input) leave the program politely, and database
  problems show a message instead of crashing the menu.

```mermaid
flowchart TD
    A(["Start: python main.py"]) --> B["Create the tables if needed"]
    B --> C{"First run? No accounts yet"}
    C -- Yes --> D["Create the organizer account"]
    C -- No --> E["Welcome screen"]
    D -- "Created: already logged in" --> M
    D -- Skipped --> E
    E --> F{"Log in, sign up or exit?"}
    F -- "Login or sign-up works" --> M
    F -- "Wrong details" --> E
    F -- Exit --> Z(["Goodbye"])
    M["Main menu"] --> G{"Choice 0-7"}
    G -- "0 Exit" --> Z
    G -- "1 View, 2 Search" --> P1{"Tradition or event?"}
    P1 -- Back --> M
    P1 -- "Tradition / Event" --> R["Show the results"]
    R --> M
    G -- "6 Summary report" --> S["Show the report"]
    S --> M
    G -- "3 Add, 4 Update, 5 Delete" --> K{"Does the role allow it?"}
    K -- No --> N["Permission denied: no questions asked"]
    N --> M
    K -- Yes --> P2{"Tradition or event?"}
    P2 -- Back --> M
    P2 -- "Tradition / Event" --> Q["Ask for the details, check each answer, confirm, save"]
    Q --> M
    G -- "7 Log out" --> E
```

> The flowchart above is a text diagram that GitHub draws by itself. If the team
> has a designed flowchart image, add it to a `docs/` folder and link it here.

## Project structure

```
main.py                    entry point (Deng)
ui/
    menus.py               Menu: the user journey (Davina)
services/
    base.py                shared create, read, update, delete logic
    tradition_service.py   rules for traditions
    event_service.py       rules for events
    auth_service.py        sign-up and login
    permissions.py         what each role may do
    errors.py              PermissionDenied, NotFoundError, AuthError
utils/
    validators.py          clean_text, clean_date, clean_record_id, clean_choice
database/
    connection.py          connecting, sessions, DatabaseError
    schema.py              the tables
    repository.py          all the SQL
tests/
    test_heritage.py       validators, services and database (Esther)
    test_auth.py           accounts and passwords
    test_menu.py           the whole user journey with scripted keystrokes
```

## Safety notes

- **SQL injection:** every query uses placeholders. The few column names that
  appear in SQL text come from fixed lists in `database/repository.py`. A search
  for `%` or `_` is treated as plain characters.
- **Passwords:** never stored as typed. Each one is salted and hashed with
  PBKDF2-SHA256 and compared in constant time. A wrong username and a wrong
  password give the same message.
- **No built-in passwords:** the organizer account is created by whoever runs
  the app first, so no default login is shipped in the code.
- **Input checks:** required fields, maximum lengths, a fixed list of
  categories, real calendar dates (`YYYY-MM-DD`), and a related tradition that
  must exist. A bad answer is explained and asked again.
- **Deleting a tradition** keeps its events; they only lose the link.
