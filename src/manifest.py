"""Manifest: generate cdm_lakehouse/model.json from schema.py and the configuration (Step 3).

model.json is the catalog of the CDM folder: it holds no data, it describes the CSV files
(columns, data types, where the files are, how the tables are connected).
It is generated from schema.py, never written by hand, so it always matches the data.
"""

import csv
import json
import logging
from pathlib import Path

from src.config import PipelineConfig
from src.schema import ENTITIES, RELATIONSHIPS, Entity, Relationship

logger = logging.getLogger(__name__)

MANIFEST_FILE = "model.json"

# ---------------------------------------------------------------------------
# Part 1: one entity (one table)
# ---------------------------------------------------------------------------


# Describe one entity: name, description, its columns and its data file (the partition).
def build_entity(entity: Entity, config: PipelineConfig) -> dict:
    attributes = [
        {
            "name": attribute.name,
            "dataType": attribute.data_type,
            "description": attribute.description,
        }
        for attribute in entity.attributes
    ]
    partition = {
        "name": f"{entity.name}Partitions",
        "location": entity.location,  # relative to model.json, e.g. "Contact/Contact.csv"
        "fileFormatSettings": {
            "$type": "CsvFormatSettings",
            "columnHeaders": True,  # load writes the header row
            "delimiter": config.csv_delimiter,  # the same delimiter load uses
        },
    }
    return {
        "$type": "LocalEntity",
        "name": entity.name,
        "description": entity.description,
        "attributes": attributes,
        "partitions": [partition],
    }


# ---------------------------------------------------------------------------
# Part 2: one relationship (foreign key)
# ---------------------------------------------------------------------------


# Describe one relationship: "from" is the foreign key side, "to" is the primary key side.
def build_relationship(relationship: Relationship) -> dict:
    return {
        "$type": "SingleKeyRelationship",
        "name": relationship.name,
        "fromAttribute": {
            "entityName": relationship.from_entity,
            "attributeName": relationship.from_attribute,
        },
        "toAttribute": {
            "entityName": relationship.to_entity,
            "attributeName": relationship.to_attribute,
        },
    }


# ---------------------------------------------------------------------------
# Part 3: the whole manifest
# ---------------------------------------------------------------------------


# Put everything together: header from the configuration, tables and relationships from schema.
def build_manifest(config: PipelineConfig) -> dict:
    return {
        "name": config.manifest_name,
        "description": config.manifest_description,
        "version": config.manifest_version,
        "entities": [build_entity(entity, config) for entity in ENTITIES],
        "relationships": [build_relationship(relationship) for relationship in RELATIONSHIPS],
    }


# ---------------------------------------------------------------------------
# Part 4: check that model.json matches the data files (before it is written)
# ---------------------------------------------------------------------------


# Read only the first row (the header) of a CSV file.
def read_header(path: Path, delimiter: str, encoding: str) -> list[str]:
    with path.open(encoding=encoding, newline="") as file:
        return next(csv.reader(file, delimiter=delimiter), [])


# Check the catalog against the files: every partition exists, its header equals the
# attributes, and every relationship points to an existing column. Collects all problems.
def check_manifest(manifest: dict, config: PipelineConfig) -> None:
    """Raise ValueError if model.json would describe something that is not in the data."""
    problems = []
    columns_by_entity = {}

    # Check 1 and 2: each partition file exists and its header equals the attributes
    for entity in manifest["entities"]:
        attribute_names = [attribute["name"] for attribute in entity["attributes"]]
        columns_by_entity[entity["name"]] = attribute_names
        for partition in entity["partitions"]:
            path = config.lakehouse_dir / partition["location"]
            if not path.exists():
                problems.append(f"{partition['location']} is missing")
                continue
            delimiter = partition["fileFormatSettings"]["delimiter"]
            if read_header(path, delimiter, config.csv_encoding) != attribute_names:
                problems.append(f"header of {partition['location']} does not match the attributes")

    # Check 3: both sides of every relationship point to an existing column
    for relationship in manifest["relationships"]:
        for side in ("fromAttribute", "toAttribute"):
            entity_name = relationship[side]["entityName"]
            attribute_name = relationship[side]["attributeName"]
            if attribute_name not in columns_by_entity.get(entity_name, []):
                problems.append(f"{relationship['name']}: {entity_name}.{attribute_name} not found")

    if problems:
        raise ValueError("model.json does not match the data: " + "; ".join(problems))
    logger.info("Manifest checked: %d entities match their data files", len(columns_by_entity))


# ---------------------------------------------------------------------------
# Part 5: write model.json
# ---------------------------------------------------------------------------


# Write the manifest to cdm_lakehouse/model.json, atomically (temporary file, then rename).
def write_manifest(manifest: dict, config: PipelineConfig) -> Path:
    path = config.lakehouse_dir / MANIFEST_FILE  # next to the Contact/ and SalesOrder/ folders
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)  # one step: readers see the old file or the new one, never half
    logger.info("Manifest written to %s", path.name)
    return path
