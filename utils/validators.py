"""Checks for what the user types.

Each function returns the cleaned value, or raises ValidationError
with a message we can show to the user.
"""
from datetime import datetime

MAX_RECORD_ID = 2 ** 63 - 1


class ValidationError(ValueError):
    """The user typed something that is not allowed."""


def clean_text(value, label="This field", max_length=100, required=True):
    """Trim the text and check it is there and not too long."""
    text = "" if value is None else str(value).strip()
    if text == "":
        if required:
            raise ValidationError("{} cannot be empty.".format(label))
        return ""
    if len(text) > max_length:
        raise ValidationError(
            "{} must be at most {} characters.".format(label, max_length))
    return text


def clean_date(value, label="Date"):
    """Check a YYYY-MM-DD date (it must be a real day) and return it."""
    text = "" if value is None else str(value).strip()
    if text == "":
        raise ValidationError("{} cannot be empty.".format(label))
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(
            "{} must be a real date in the format YYYY-MM-DD, "
            "for example 2026-08-07.".format(label))
    # strptime accepts 2026-8-7, so give back the 2026-08-07 form
    return parsed.strftime("%Y-%m-%d")


def clean_record_id(value, label="ID"):
    """Check an ID (a whole number from 1) and return it as an int."""
    if isinstance(value, bool):
        raise ValidationError("{} must be a whole number.".format(label))
    if isinstance(value, int):
        number = value
    else:
        text = "" if value is None else str(value).strip()
        if not (text.isascii() and text.isdigit()):
            raise ValidationError("{} must be a whole number.".format(label))
        number = int(text)
    if number < 1 or number > MAX_RECORD_ID:
        raise ValidationError(
            "{} must be a whole number of 1 or more.".format(label))
    return number


def clean_choice(value, choices, label="This field"):
    """Check the value is one of the choices (any case).

    Returns it in lower case.
    """
    text = "" if value is None else str(value).strip().lower()
    if text == "":
        raise ValidationError("{} cannot be empty.".format(label))
    if text not in choices:
        raise ValidationError(
            "{} must be one of: {}.".format(label, ", ".join(choices)))
    return text
