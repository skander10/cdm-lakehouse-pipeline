"""End-to-end test: run the whole pipeline on the real raw files, like python -m src.main."""

import csv
from pathlib import Path

from src.config import PROJECT_ROOT, PipelineConfig
from src.main import main


# Helper: run the whole pipeline, but write every output into an empty test folder
# (same folder layout as the repository).
def run_pipeline(tmp_path: Path) -> PipelineConfig:
    config = PipelineConfig(
        lakehouse_dir=tmp_path / "cdm_lakehouse",
        quarantine_dir=tmp_path / "data" / "quarantine",
        logs_dir=tmp_path / "logs",
        reports_dir=tmp_path / "reports",
    )
    main(config)
    return config


# Helper: read a CSV file as a list of rows (each row: column name -> value).
def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


# One run creates every output: the CDM folder, quarantine, quality report and log.
def test_pipeline_creates_all_outputs(tmp_path: Path) -> None:
    config = run_pipeline(tmp_path)

    assert (config.lakehouse_dir / "Contact/Contact.csv").exists()
    assert (config.lakehouse_dir / "SalesOrder/SalesOrder.csv").exists()
    assert (config.lakehouse_dir / "model.json").exists()
    assert (config.quarantine_dir / "quarantine.csv").exists()
    assert (config.reports_dir / "data_quality_report.md").exists()
    assert "Pipeline finished" in (config.logs_dir / "pipeline.log").read_text()


# The output files in the repository are exactly what the code produces (nothing outdated).
def test_committed_output_is_up_to_date(tmp_path: Path) -> None:
    run_pipeline(tmp_path)

    outputs = [
        "cdm_lakehouse/Contact/Contact.csv",
        "cdm_lakehouse/SalesOrder/SalesOrder.csv",
        "cdm_lakehouse/model.json",
        "data/quarantine/quarantine.csv",
        "reports/data_quality_report.md",
    ]
    for name in outputs:
        produced = (tmp_path / name).read_text()
        committed = (PROJECT_ROOT / name).read_text()
        assert produced == committed, f"{name} is outdated, run python -m src.main"


# Every order in SalesOrder.csv belongs to a contact in Contact.csv (no orphan got through).
def test_every_order_has_an_existing_contact(tmp_path: Path) -> None:
    config = run_pipeline(tmp_path)
    contacts = read_rows(config.lakehouse_dir / "Contact/Contact.csv")
    orders = read_rows(config.lakehouse_dir / "SalesOrder/SalesOrder.csv")

    contact_ids = {contact["contactid"] for contact in contacts}
    assert all(order["customerid"] in contact_ids for order in orders)
