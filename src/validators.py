"""Validators: small rules that clean and check ONE value.

They are the toolbox of the transformation step. They do not log and do not decide about the
quarantine. They only return the clean value, or None if the value cannot be used.
The transformation decides what happens next.
"""

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

# Status text -> CDM statecode (assignment: active -> 0, inactive -> 1).
STATUS_CODES = {"active": 0, "inactive": 1}

# Pragmatic e-mail rule: name@domain.ending, no spaces, exactly one @, ending >= 2 letters.
# Deliberately not too strict, so that no valid address is lost.
EMAIL_PATTERN = r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}"

# Target timestamp format of the assignment: ISO 8601 in UTC.
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


# Tool 1 - Name: split a full name into first name and last name.
def split_name(raw: str) -> tuple[str | None, str | None]:
    """Split a full name: first word = first name, the rest = last name.

    A single word gives no last name; an empty value gives neither.
    Known limit: compound first names (e.g. "Maria del Carmen") are split after the first word.
    """
    parts = raw.split()

    if not parts:
        return None, None

    first_name = parts[0]
    last_name = " ".join(parts[1:]) or None

    return first_name, last_name


# Tool 2 - E-mail: clean an e-mail address and check its format.
def normalize_email(raw: str) -> str | None:
    """Clean an e-mail (trim, lowercase) and check its format. Invalid values return None.

    Cleaning comes first, so that e.g. upper-case addresses are not rejected.
    """
    email = raw.strip().lower()

    if re.fullmatch(EMAIL_PATTERN, email):
        return email

    return None


# Tool 3 - Timestamp: turn a date/time text into ISO 8601 UTC.
def parse_timestamp(raw: str, default_timezone: str = "UTC") -> tuple[str | None, bool]:
    """Convert a timestamp to "YYYY-MM-DDTHH:MM:SSZ" (UTC).

    Returns (timestamp, timezone_assumed). If the value has no time zone, default_timezone is
    assumed and timezone_assumed is True. A value that is not a date returns (None, False).
    """
    # Step 1: read the text as a date; if it is not a date, return None
    try:
        moment = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None, False

    # Step 2: check whether the text contains a time zone
    timezone_assumed = moment.tzinfo is None

    # Step 3: no time zone in the text -> use the default time zone from the configuration.
    # No try/except here on purpose: a misspelled default time zone is a setting error
    # and must stop the pipeline (fail fast) instead of silently emptying every date.
    if timezone_assumed:
        moment = moment.replace(tzinfo=ZoneInfo(default_timezone))

    # Step 4: convert to UTC and write it in the format of the assignment
    return moment.astimezone(UTC).strftime(TIMESTAMP_FORMAT), timezone_assumed


# Tool 4 - Status: turn a status text into the CDM statecode (0 or 1).
def normalize_status(raw: str) -> int | None:
    """Map a status text to its statecode. Unknown or empty values return None."""
    return STATUS_CODES.get(raw.strip().lower())


# Tool 5 - Amount: turn a text into an exact decimal number.
def parse_amount(raw: str) -> Decimal | None:
    """Convert a text to an exact Decimal. Empty, non-numeric, NaN or infinite values return None.

    Negative amounts are valid numbers (they can be credit notes); flagging them is a business
    decision made in the transformation.
    """
    try:
        amount = Decimal(raw.strip())
    except InvalidOperation:
        return None
    return amount if amount.is_finite() else None
