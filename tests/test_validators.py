"""Tests for the validators: one value in, check the result. No files needed."""

from decimal import Decimal
from zoneinfo import ZoneInfoNotFoundError

import pytest

from src.validators import (
    normalize_email,
    normalize_status,
    parse_amount,
    parse_timestamp,
    split_name,
)

# --- Tool 1: Name ---


# A normal name is split into first and last name; spaces around and inside are ignored.
def test_name_is_split_into_first_and_last_name() -> None:
    assert split_name("Jane Doe") == ("Jane", "Doe")
    assert split_name("  Charlie Brown") == ("Charlie", "Brown")
    assert split_name("Jane   Doe") == ("Jane", "Doe")


# A last name with several words stays together.
def test_multi_word_last_name_stays_together() -> None:
    assert split_name("Ludwig van Beethoven") == ("Ludwig", "van Beethoven")


# One word gives no last name; an empty value gives neither.
def test_single_word_or_empty_name() -> None:
    assert split_name("Madonna") == ("Madonna", None)
    assert split_name("") == (None, None)
    assert split_name("   ") == (None, None)


# --- Tool 2: E-mail ---


# Valid addresses are kept, also unusual ones with "+" (deliberately not too strict).
def test_valid_email_is_kept() -> None:
    assert normalize_email("jane.doe@example.com") == "jane.doe@example.com"
    assert normalize_email("jane+news@example.com") == "jane+news@example.com"


# Cleaning comes before checking: upper case and outer spaces are fixed, not rejected.
def test_email_is_cleaned_before_checking() -> None:
    assert normalize_email("JOHN.SMITH@DOMAIN.COM") == "john.smith@domain.com"
    assert normalize_email(" bob.ross@paint.org ") == "bob.ross@paint.org"


# Invalid addresses return None.
def test_invalid_email_returns_none() -> None:
    assert normalize_email("invalid-email-format") is None  # no @
    assert normalize_email("a@b") is None  # no dot in the domain
    assert normalize_email("jane doe@x.com") is None  # space inside
    assert normalize_email("jane@@x.com") is None  # two @
    assert normalize_email("") is None


# --- Tool 3: Timestamp ---


# A timestamp with Z is already UTC: kept, no time zone assumed.
def test_utc_timestamp_is_kept() -> None:
    assert parse_timestamp("2023-01-15T10:30:00Z") == ("2023-01-15T10:30:00Z", False)


# A timestamp with another time zone is converted to UTC (same moment, other notation).
def test_timestamp_with_offset_is_converted_to_utc() -> None:
    assert parse_timestamp("2023-07-01T10:00:00+02:00") == ("2023-07-01T08:00:00Z", False)


# No time zone: the default (UTC) is assumed; a date only gets 00:00:00.
def test_missing_time_zone_is_assumed() -> None:
    assert parse_timestamp("2023-02-20 14:15:00") == ("2023-02-20T14:15:00Z", True)
    assert parse_timestamp("2023-03-05") == ("2023-03-05T00:00:00Z", True)


# Another default time zone from the configuration is used, including summer time.
def test_other_default_time_zone_is_used() -> None:
    assert parse_timestamp("2023-02-20 14:15:00", "Europe/Berlin") == (
        "2023-02-20T13:15:00Z",
        True,
    )  # winter: +1 hour
    assert parse_timestamp("2023-07-01 14:15:00", "Europe/Berlin") == (
        "2023-07-01T12:15:00Z",
        True,
    )  # summer: +2 hours


# Values that are not a date return None.
def test_invalid_timestamp_returns_none() -> None:
    assert parse_timestamp("eve.adams@example.com") == (None, False)
    assert parse_timestamp("") == (None, False)
    assert parse_timestamp("2023-02-30") == (None, False)  # 30 February does not exist


# A misspelled default time zone is a setting error: it must fail loudly (fail fast).
def test_misspelled_default_time_zone_fails() -> None:
    with pytest.raises(ZoneInfoNotFoundError):
        parse_timestamp("2023-02-20 14:15:00", "Europe/Berln")


# --- Tool 4: Status ---


# The two known values are mapped as in the assignment.
def test_status_is_mapped_to_statecode() -> None:
    assert normalize_status("active") == 0
    assert normalize_status("inactive") == 1


# Upper/lower case and outer spaces do not matter.
def test_status_ignores_case_and_spaces() -> None:
    assert normalize_status("ACTIVE") == 0
    assert normalize_status(" Inactive ") == 1


# Unknown or empty values return None instead of guessing.
def test_unknown_or_empty_status_returns_none() -> None:
    assert normalize_status("pending") is None
    assert normalize_status("") is None


# --- Tool 5: Amount ---


# A valid amount becomes an exact Decimal, outer spaces are ignored.
def test_amount_is_converted_to_exact_decimal() -> None:
    assert parse_amount("1200.00") == Decimal("1200.00")
    assert parse_amount(" 49.99 ") == Decimal("49.99")


# A negative amount is a valid number (possible credit note); the warning is made in transform.
def test_negative_amount_is_a_valid_number() -> None:
    assert parse_amount("-49.99") == Decimal("-49.99")


# Empty, non-numeric, NaN or infinite values return None.
def test_invalid_amount_returns_none() -> None:
    assert parse_amount("abc") is None
    assert parse_amount("") is None
    assert parse_amount("NaN") is None
    assert parse_amount("Infinity") is None