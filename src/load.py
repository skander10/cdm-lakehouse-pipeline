"""Load: write the clean tables into the CDM folder and the rejected records into the quarantine.

Assignment Step 2 (Storage): cdm_lakehouse/Contact/Contact.csv and
cdm_lakehouse/SalesOrder/SalesOrder.csv. Every run overwrites the files (idempotent), and every
file is written atomically, so a reader never sees a half-written file.
"""

import logging
from pathlib import Path

import pandas as pd

from src.config import PipelineConfig
from src.extract import RejectedRow
from src.schema import CONTACT, SALES_ORDER, Entity
from src.transform import QuarantinedRecord

logger = logging.getLogger(__name__)

QUARANTINE_FILE = "quarantine.csv"
QUARANTINE_COLUMNS = ["stage", "entity", "record_id", "reason", "raw_values"]


# ---------------------------------------------------------------------------
# Part 1: write one CSV file safely
# ---------------------------------------------------------------------------


# Write a table to a CSV file: first into a temporary file, then rename it in one step.
def write_csv(table: pd.DataFrame, path: Path, config: PipelineConfig) -> None:
    """Write atomically: if the run stops in the middle, the old file stays complete."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    table.to_csv(
        temp_path,
        index=False,
        sep=config.csv_delimiter,
        encoding=config.csv_encoding,
        lineterminator="\n",
    )
    temp_path.replace(path)  # one step: readers see the old file or the new one, never half



# ---------------------------------------------------------------------------
# Part 2: the CDM tables (assignment Step 2)
# ---------------------------------------------------------------------------


# Write one entity to cdm_lakehouse/<Entity>/<Entity>.csv, columns in the order of the schema.
def write_entity(table: pd.DataFrame, entity: Entity, config: PipelineConfig) -> Path:
    path = config.lakehouse_dir / entity.location
    write_csv(table[entity.column_names], path, config)
    logger.info("%s: %d rows written to %s", entity.name, len(table), entity.location)
    return path


# Write both CDM tables.
def write_cdm_tables(
    contacts: pd.DataFrame, sales_orders: pd.DataFrame, config: PipelineConfig
) -> None:
    write_entity(contacts, CONTACT, config)
    write_entity(sales_orders, SALES_ORDER, config)



# ---------------------------------------------------------------------------
# Part 3: the quarantine (records rejected by extract and by transform, in one file)
# ---------------------------------------------------------------------------


# Collect all rejected records in one table with the same columns.
def quarantine_table(
    extract_rejected: dict[str, list[RejectedRow]],
    transform_quarantined: list[QuarantinedRecord],
) -> pd.DataFrame:
    """extract_rejected maps the entity name (e.g. "Contact") to the rows extract rejected."""
    rows = []
    for entity, rejected_rows in extract_rejected.items():
        for row in rejected_rows:
            rows.append(
                {
                    "stage": "extract",
                    "entity": entity,
                    "record_id": "",
                    "reason": f"line {row.line_number}: wrong number of fields",
                    "raw_values": ",".join(row.values),
                }
            )
    for record in transform_quarantined:
        rows.append(
            {
                "stage": "transform",
                "entity": record.entity,
                "record_id": record.record_id,
                "reason": record.reason,
                "raw_values": ",".join(record.values.values()),
            }
        )
    return pd.DataFrame(rows, columns=QUARANTINE_COLUMNS, dtype=object)


# Write the quarantine file (always, so an old file from a previous run never stays behind).
def write_quarantine(table: pd.DataFrame, config: PipelineConfig) -> Path:
    path = config.quarantine_dir / QUARANTINE_FILE
    write_csv(table, path, config)
    logger.info("Quarantine: %d records written to %s", len(table), path.name)
    return path