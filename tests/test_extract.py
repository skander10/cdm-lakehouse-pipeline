"""Tests for the extract step."""

from pathlib import Path

import pytest

from src.config import PipelineConfig
from src.extract import CUSTOMER_COLUMNS, extract_customers, extract_orders, read_raw_csv


# Test 1: complete rows pass through unchanged
def test_complete_customer_rows_are_read_unchanged() -> None:
    result = extract_customers(PipelineConfig())

    assert result.data.values.tolist() == [
        ["CST-001", "Jane Doe", "jane.doe@example.com", "2023-01-15T10:30:00Z", "active"],
        ["CST-002", "John Smith", "JOHN.SMITH@DOMAIN.COM", "2023-02-20 14:15:00", "active"],
        ["CST-003", "Alice Vance", "invalid-email-format", "2023-03-05", "inactive"],
        ["CST-004", "Bob Ross", "bob.ross@paint.org", "2023-04-12T08:00:00Z", "ACTIVE"],
    ]


# Test 2: a row split across two lines is rejected
def test_row_split_across_two_lines_is_rejected() -> None:
    result = extract_customers(PipelineConfig())

    assert [row.line_number for row in result.rejected] == [6, 7]
    assert result.rejected[0].values == ["CST-005", "  Charlie Brown"]


# Test 3: missing values are kept, the transformation decides about them
def test_missing_values_are_kept_for_the_transformation(tmp_path: Path) -> None:
    # Empty values (all commas present) are a content question, decided in the transformation.
    # This includes an empty ID: the transformation will send that row to the quarantine.
    raw_file = tmp_path / "customers.csv"
    raw_file.write_text(
        "cust_id,full_name,email_addr,signup_date,user_status\n"
        "CST-006,Dana Scott,,,active\n"
        ",Eve Adams,eve.adams@example.com,2023-08-01T10:00:00Z,active\n"
    )
    result = read_raw_csv(raw_file, CUSTOMER_COLUMNS)

    assert len(result.data) == 2
    assert result.rejected == []


# Test 4: orders are read unchanged, every value as text
def test_orders_are_read_unchanged_as_text() -> None:
    result = extract_orders(PipelineConfig())

    assert result.rejected == []
    assert result.data.values.tolist() == [
        ["ORD-1001", "CST-001", "250.50", "2023-06-01T09:15:00Z"],
        ["ORD-1002", "CST-001", "49.99", "2023-06-02T11:20:00Z"],
        ["ORD-1003", "CST-002", "1200.00", "2023-06-03T16:45:00Z"],
        ["ORD-1004", "CST-004", "15.75", "2023-06-05T18:00:00Z"],
        ["ORD-1005", "CST-999", "99.00", "2023-06-06T10:00:00Z"],
    ]


# Test 5: a file with the wrong header is stopped immediately
def test_file_with_wrong_header_is_rejected(tmp_path: Path) -> None:
    wrong_file = tmp_path / "customers.csv"
    wrong_file.write_text("id,name,email\nCST-001,Jane Doe,jane.doe@example.com\n")

    with pytest.raises(ValueError, match="expected columns"):
        read_raw_csv(wrong_file, CUSTOMER_COLUMNS)
