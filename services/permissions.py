"""The roles and what each one is allowed to do."""

# organizers can do everything, volunteers can only view, search and add
ROLE_PERMISSIONS = {
    "organizer": {"view", "search", "report", "add", "update", "delete"},
    "volunteer": {"view", "search", "report", "add"},
}

ROLE_DESCRIPTIONS = {
    "organizer": "Organizer (view, add, update and delete records)",
    "volunteer": "Volunteer (view, search and add records)",
}

ACTION_LABELS = {
    "add": "add records",
    "update": "update records",
    "delete": "delete records",
}


def can(role, action):
    """Return True if the role is allowed to do the action."""
    return action in ROLE_PERMISSIONS.get(role, ())
