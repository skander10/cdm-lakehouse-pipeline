"""Extract: read the raw CSV files into DataFrames.

Rows with the wrong number of fields (for example a row split across two lines) are not
repaired: they are rejected and later written to the quarantine. We never guess.
No value is changed here: cleaning the content is the job of the transformation.
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.config import PipelineConfig

logger = logging.getLogger(__name__)

# Expected columns of the raw files, as given in the assignment.
CUSTOMER_COLUMNS = ["cust_id", "full_name", "email_addr", "signup_date", "user_status"]
ORDER_COLUMNS = ["tx_id", "customer_id", "amount_usd", "tx_timestamp"]


@dataclass
class RejectedRow:
    """A raw row that is not a complete record."""

    line_number: int  # line in the raw file, so a person can find it
    values: list[str]  # the row exactly as read


@dataclass
class ExtractResult:
    """The outcome of reading one raw file."""

    data: pd.DataFrame  # complete rows, every value as text
    rejected: list[RejectedRow]  # rows with the wrong number of fields, for the quarantine


def read_raw_csv(
    path: Path, expected_columns: list[str], encoding: str = "utf-8", delimiter: str = ","
) -> ExtractResult:
    """Read a raw CSV file: check the header, keep complete rows, reject all others."""
    # Step 1: prepare the two result lists
    complete_rows: list[list[str]] = []
    rejected: list[RejectedRow] = []

    # Step 2: open the file and check the header
    with path.open(newline="", encoding=encoding) as file:
        reader = csv.reader(file, delimiter=delimiter)

        header = next(reader, [])
        if header != expected_columns:
            raise ValueError(f"{path.name}: expected columns {expected_columns}, found {header}")

        # Step 3: check each row: complete rows are kept, all others rejected
        for row in reader:
            if not row:
                continue  # skip empty lines
            if len(row) == len(expected_columns):
                complete_rows.append(row)
            else:
                rejected.append(RejectedRow(line_number=reader.line_num, values=row))
                logger.warning(
                    "%s: line %d rejected (expected %d fields, found %d)",
                    path.name,
                    reader.line_num,
                    len(expected_columns),
                    len(row),
                )

    # Step 4: build the result
    logger.info("%s: %d rows read, %d rejected", path.name, len(complete_rows), len(rejected))
    data = pd.DataFrame(complete_rows, columns=expected_columns, dtype=str)
    return ExtractResult(data=data, rejected=rejected)


# Entry points for our two raw files


def extract_customers(config: PipelineConfig) -> ExtractResult:
    """Read raw_customers.csv."""
    return read_raw_csv(
        config.customers_path, CUSTOMER_COLUMNS, config.csv_encoding, config.csv_delimiter
    )


def extract_orders(config: PipelineConfig) -> ExtractResult:
    """Read raw_orders.csv."""
    return read_raw_csv(
        config.orders_path, ORDER_COLUMNS, config.csv_encoding, config.csv_delimiter
    )