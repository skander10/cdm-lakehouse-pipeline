"""Tests for the load step: files are written correctly, safely and repeatably."""

from decimal import Decimal
from pathlib import Path

import pandas as pd

from src.config import PipelineConfig
from src.extract import RejectedRow
from src.load import quarantine_table, write_cdm_tables, write_quarantine
from src.schema import CONTACT, SALES_ORDER
from src.transform import QuarantinedRecord


# Helper: a configuration that writes into an empty test folder, never into the real one.
def make_config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(lakehouse_dir=tmp_path / "cdm", quarantine_dir=tmp_path / "quarantine")


# Helper: one clean contact and one clean order, as transform delivers them.
def clean_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    contacts = pd.DataFrame(
        [["CST-003", "Alice", "Vance", None, "2023-03-05T00:00:00Z", 1]],
        columns=CONTACT.column_names,
        dtype=object,
    )
    orders = pd.DataFrame(
        [["ORD-1003", "CST-002", Decimal("1200.00"), "2023-06-03T16:45:00Z"]],
        columns=SALES_ORDER.column_names,
        dtype=object,
    )
    return contacts, orders


# The CSV files are written to the CDM folders with the exact content (empty value -> empty field).
def test_cdm_tables_are_written(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    contacts, orders = clean_tables()

    write_cdm_tables(contacts, orders, config)

    assert (config.lakehouse_dir / "Contact/Contact.csv").read_text() == (
        "contactid,firstname,lastname,emailaddress1,createdon,statecode\n"
        "CST-003,Alice,Vance,,2023-03-05T00:00:00Z,1\n"
    )
    assert (config.lakehouse_dir / "SalesOrder/SalesOrder.csv").read_text() == (
        "salesorderid,customerid,totalamount,createdon\n"
        "ORD-1003,CST-002,1200.00,2023-06-03T16:45:00Z\n"
    )


# Running twice gives the same files (idempotent), and no temporary file is left behind.
def test_writing_twice_gives_the_same_result(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    contacts, orders = clean_tables()
    contact_file = config.lakehouse_dir / "Contact/Contact.csv"

    write_cdm_tables(contacts, orders, config)
    first_run = contact_file.read_text()
    write_cdm_tables(contacts, orders, config)

    assert contact_file.read_text() == first_run
    assert list(tmp_path.rglob("*.tmp")) == []


# Records rejected by extract and by transform end up together in one quarantine file.
def test_quarantine_contains_records_from_extract_and_transform(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    table = quarantine_table(
        {"Contact": [RejectedRow(line_number=6, values=["CST-005", "  Charlie Brown"])]},
        [
            QuarantinedRecord(
                "SalesOrder",
                "ORD-1005",
                "orphan: customer CST-999 does not exist",
                {"tx_id": "ORD-1005", "customer_id": "CST-999"},
            )
        ],
    )

    path = write_quarantine(table, config)

    assert path.read_text() == (
        "stage,entity,record_id,reason,raw_values\n"
        'extract,Contact,,line 6: wrong number of fields,"CST-005,  Charlie Brown"\n'
        'transform,SalesOrder,ORD-1005,orphan: customer CST-999 does not exist,"ORD-1005,CST-999"\n'
    )
