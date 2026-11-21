"""Entry point for the Community Culture and Heritage Management System.

Run with:  python main.py

Owner: Deng
"""
import sys

from database.connection import DatabaseError
from database.schema import init_db
from services.auth_service import AuthService
from services.event_service import EventService
from services.tradition_service import TraditionService
from ui.menus import Menu


def main():
    """Create the database if needed, then start the menu loop."""
    try:
        init_db()
    except DatabaseError as exc:
        print(f"Cannot start the application: {exc}")
        sys.exit(1)
    menu = Menu(
        traditions=TraditionService(),
        events=EventService(),
        auth=AuthService(),
    )
    menu.run()


if __name__ == "__main__":
    main()
