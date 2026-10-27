"""Tests for the transform step: raw tables in, CDM tables + quarantine + issues out."""

from decimal import Decimal

import pandas as pd

from src.config import PipelineConfig
from src.extract import CUSTOMER_COLUMNS, ORDER_COLUMNS, extract_customers, extract_orders
from src.transform import TransformResult, transform


# Helper: build a small raw table (all text) for one test, like extract would deliver it.
def raw_table(columns: list[str], rows: list[list[str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns, dtype=str)


# Helper: run transform on the real raw files of the assignment. (From extract)
def transform_real_data() -> TransformResult:
    config = PipelineConfig()
    customers = extract_customers(config).data
    orders = extract_orders(config).data
    return transform(customers, orders, config.default_timezone)


# --- Part 1: the real data of the assignment ---


# The Contact table is exactly what the assignment asks for (CST-005 was rejected by extract).
def test_contacts_from_real_data() -> None:
    result = transform_real_data()

    assert result.contacts.values.tolist() == [
        ["CST-001", "Jane", "Doe", "jane.doe@example.com", "2023-01-15T10:30:00Z", 0],
        ["CST-002", "John", "Smith", "john.smith@domain.com", "2023-02-20T14:15:00Z", 0],
        ["CST-003", "Alice", "Vance", None, "2023-03-05T00:00:00Z", 1],
        ["CST-004", "Bob", "Ross", "bob.ross@paint.org", "2023-04-12T08:00:00Z", 0],
    ]


# The SalesOrder table has 4 orders; the orphan ORD-1005 (customer CST-999) is quarantined.
def test_sales_orders_from_real_data() -> None:
    result = transform_real_data()

    assert result.sales_orders.values.tolist() == [
        ["ORD-1001", "CST-001", Decimal("250.50"), "2023-06-01T09:15:00Z"],
        ["ORD-1002", "CST-001", Decimal("49.99"), "2023-06-02T11:20:00Z"],
        ["ORD-1003", "CST-002", Decimal("1200.00"), "2023-06-03T16:45:00Z"],
        ["ORD-1004", "CST-004", Decimal("15.75"), "2023-06-05T18:00:00Z"],
    ]
    assert [(q.record_id, q.reason) for q in result.quarantined] == [
        ("ORD-1005", "orphan: customer CST-999 does not exist")
    ]


# Every problem in the real data is reported: invalid e-mail and the two assumed time zones.
def test_issues_from_real_data() -> None:
    result = transform_real_data()

    assert [(i.record_id, i.field, i.message) for i in result.issues] == [
        ("CST-002", "createdon", "no time zone given, UTC assumed"),
        ("CST-003", "emailaddress1", "invalid, set to null"),
        ("CST-003", "createdon", "no time zone given, UTC assumed"),
    ]


# --- Part 2: rules that our real data does not contain ---


# Required contactid: a missing or duplicate ID goes to the quarantine.
def test_contact_without_id_or_duplicate_is_quarantined() -> None:
    customers = raw_table(
        CUSTOMER_COLUMNS,
        [
            ["CST-006", "Dana Scott", "dana@example.com", "2023-06-01T10:00:00Z", "active"],
            ["", "Eve Adams", "eve@example.com", "2023-06-02T10:00:00Z", "active"],
            ["CST-006", "Dana Copy", "copy@example.com", "2023-06-03T10:00:00Z", "active"],
        ],
    )
    result = transform(customers, raw_table(ORDER_COLUMNS, []), "UTC")

    assert result.contacts["contactid"].tolist() == ["CST-006"]
    assert [(q.record_id, q.reason) for q in result.quarantined] == [
        ("", "id is missing"),
        ("CST-006", "duplicate id"),
    ]


# Optional values: unknown status and a single-word name are left empty with a warning.
def test_optional_values_are_left_empty_with_warning() -> None:
    customers = raw_table(
        CUSTOMER_COLUMNS,
        [["CST-007", "Madonna", "madonna@example.com", "2023-06-01T10:00:00Z", "pending"]],
    )
    result = transform(customers, raw_table(ORDER_COLUMNS, []), "UTC")

    assert result.contacts.values.tolist() == [
        ["CST-007", "Madonna", None, "madonna@example.com", "2023-06-01T10:00:00Z", None]
    ]
    assert [(i.record_id, i.field, i.message) for i in result.issues] == [
        ("CST-007", "lastname", "only one name part, left empty"),
        ("CST-007", "statecode", "invalid, left empty"),
    ]


# Required totalamount: invalid -> quarantine; negative -> kept with a warning.
def test_invalid_amount_is_quarantined_and_negative_amount_is_flagged() -> None:
    customers = raw_table(
        CUSTOMER_COLUMNS,
        [["CST-001", "Jane Doe", "jane@example.com", "2023-01-15T10:30:00Z", "active"]],
    )
    orders = raw_table(
        ORDER_COLUMNS,
        [
            ["ORD-2001", "CST-001", "abc", "2023-06-01T09:15:00Z"],
            ["ORD-2002", "CST-001", "-49.99", "2023-06-02T09:15:00Z"],
        ],
    )
    result = transform(customers, orders, "UTC")

    assert result.sales_orders["salesorderid"].tolist() == ["ORD-2002"]
    assert [(q.record_id, q.reason) for q in result.quarantined] == [
        ("ORD-2001", "totalamount invalid")
    ]
    assert [(i.record_id, i.field, i.message) for i in result.issues] == [
        ("ORD-2002", "totalamount", "negative amount (possible credit note)")
    ]
