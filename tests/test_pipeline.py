"""End-to-end test: run the whole pipeline on the real raw files, like python -m src.main."""

import csv
from pathlib import Path

from src.config import PROJECT_ROOT, PipelineConfig
from src.main import main


# Helper: run the whole pipeline, but write every output into an empty test folder.
def run_pipeline(tmp_path: Path) -> PipelineConfig:
    config = PipelineConfig(
        lakehouse_dir=tmp_path / "cdm_lakehouse",
        quarantine_dir=tmp_path / "quarantine",
        logs_dir=tmp_path / "logs",
    )
    main(config)
    return config


# Helper: read a CSV file as a list of rows (each row: column name -> value).
def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


# One run creates every output: the CDM folder, the quarantine file and the log.
def test_pipeline_creates_all_outputs(tmp_path: Path) -> None:
    config = run_pipeline(tmp_path)

    assert (config.lakehouse_dir / "Contact/Contact.csv").exists()
    assert (config.lakehouse_dir / "SalesOrder/SalesOrder.csv").exists()
    assert (config.lakehouse_dir / "model.json").exists()
    assert (config.quarantine_dir / "quarantine.csv").exists()
    assert "Pipeline finished" in (config.logs_dir / "pipeline.log").read_text()


# The output files in the repository are exactly what the code produces (nothing outdated).
def test_committed_output_is_up_to_date(tmp_path: Path) -> None:
    config = run_pipeline(tmp_path)

    for name in ["Contact/Contact.csv", "SalesOrder/SalesOrder.csv", "model.json"]:
        produced = (config.lakehouse_dir / name).read_text()
        committed = (PROJECT_ROOT / "cdm_lakehouse" / name).read_text()
        assert produced == committed, f"cdm_lakehouse/{name} is outdated, run python -m src.main"


# Every order in SalesOrder.csv belongs to a contact in Contact.csv (no orphan got through).
def test_every_order_has_an_existing_contact(tmp_path: Path) -> None:
    config = run_pipeline(tmp_path)
    contacts = read_rows(config.lakehouse_dir / "Contact/Contact.csv")
    orders = read_rows(config.lakehouse_dir / "SalesOrder/SalesOrder.csv")

    contact_ids = {contact["contactid"] for contact in contacts}
    assert all(order["customerid"] in contact_ids for order in orders)
