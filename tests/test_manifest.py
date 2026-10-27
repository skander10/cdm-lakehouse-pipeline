"""Tests for the manifest step: model.json is correct, written safely, checked against the data."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.config import PipelineConfig
from src.load import write_cdm_tables
from src.manifest import build_manifest, check_manifest, write_manifest
from src.schema import CONTACT, SALES_ORDER

# The model.json of the assignment (section "Expected model.json Structure Reference").
CSV_FORMAT = {"$type": "CsvFormatSettings", "columnHeaders": True, "delimiter": ","}
EXPECTED_MODEL_JSON = {
    "name": "EnterpriseDataLake",
    "description": "CDM Manifest for Ingested Customer and Sales Data",
    "version": "1.0",
    "entities": [
        {
            "$type": "LocalEntity",
            "name": "Contact",
            "description": "Standard CDM Contact entity for individual customers",
            "attributes": [
                {
                    "name": "contactid",
                    "dataType": "string",
                    "description": "Unique primary key for the contact",
                },
                {
                    "name": "firstname",
                    "dataType": "string",
                    "description": "First name of the contact",
                },
                {
                    "name": "lastname",
                    "dataType": "string",
                    "description": "Last name of the contact",
                },
                {
                    "name": "emailaddress1",
                    "dataType": "string",
                    "description": "Primary email address",
                },
                {
                    "name": "createdon",
                    "dataType": "dateTime",
                    "description": "ISO 8601 creation timestamp",
                },
                {
                    "name": "statecode",
                    "dataType": "int64",
                    "description": "Status code: 0 for Active, 1 for Inactive",
                },
            ],
            "partitions": [
                {
                    "name": "ContactPartitions",
                    "location": "Contact/Contact.csv",
                    "fileFormatSettings": CSV_FORMAT,
                }
            ],
        },
        {
            "$type": "LocalEntity",
            "name": "SalesOrder",
            "description": "Standard CDM SalesOrder entity for transactions",
            "attributes": [
                {
                    "name": "salesorderid",
                    "dataType": "string",
                    "description": "Unique order identifier",
                },
                {
                    "name": "customerid",
                    "dataType": "string",
                    "description": "Foreign key reference to Contact",
                },
                {
                    "name": "totalamount",
                    "dataType": "decimal",
                    "description": "Total order amount in USD",
                },
                {
                    "name": "createdon",
                    "dataType": "dateTime",
                    "description": "ISO 8601 transaction timestamp",
                },
            ],
            "partitions": [
                {
                    "name": "SalesOrderPartitions",
                    "location": "SalesOrder/SalesOrder.csv",
                    "fileFormatSettings": CSV_FORMAT,
                }
            ],
        },
    ],
    "relationships": [
        {
            "$type": "SingleKeyRelationship",
            "name": "Contact_SalesOrder_Relationship",
            "fromAttribute": {"entityName": "SalesOrder", "attributeName": "customerid"},
            "toAttribute": {"entityName": "Contact", "attributeName": "contactid"},
        }
    ],
}


# Helper: a configuration that writes into an empty test folder, never into the real one.
def make_config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(lakehouse_dir=tmp_path / "cdm")


# Helper: write the two CDM files with their header only (the check reads only the header).
def write_empty_tables(config: PipelineConfig) -> None:
    contacts = pd.DataFrame(columns=CONTACT.column_names)
    sales_orders = pd.DataFrame(columns=SALES_ORDER.column_names)
    write_cdm_tables(contacts, sales_orders, config)


# The generated manifest is exactly the model.json of the assignment (Step 3).
def test_manifest_matches_the_assignment_reference() -> None:
    assert build_manifest(PipelineConfig()) == EXPECTED_MODEL_JSON


# model.json is written next to the data folders, can be read back, and no temporary file is left.
def test_manifest_file_is_written(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    manifest = build_manifest(config)

    path = write_manifest(manifest, config)

    assert path == config.lakehouse_dir / "model.json"
    assert json.loads(path.read_text()) == manifest
    assert list(tmp_path.rglob("*.tmp")) == []


# The check accepts a catalog that matches the data files.
def test_check_accepts_matching_files(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    write_empty_tables(config)

    check_manifest(build_manifest(config), config)  # no error expected


# The check reports every mismatch at once: wrong header, missing file, wrong relationship.
def test_check_reports_every_problem(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    write_empty_tables(config)
    manifest = build_manifest(config)

    # Break three things on purpose
    manifest["entities"][0]["attributes"][3]["name"] = "email"  # Contact: column renamed
    (config.lakehouse_dir / "SalesOrder/SalesOrder.csv").unlink()  # SalesOrder: file deleted
    manifest["relationships"][0]["toAttribute"]["attributeName"] = "contact_id"  # wrong column

    with pytest.raises(ValueError) as error:
        check_manifest(manifest, config)

    assert str(error.value) == (
        "model.json does not match the data: "
        "header of Contact/Contact.csv does not match the attributes; "
        "SalesOrder/SalesOrder.csv is missing; "
        "Contact_SalesOrder_Relationship: Contact.contact_id not found"
    )
