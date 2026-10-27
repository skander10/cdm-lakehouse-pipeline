"""Central configuration of the pipeline.

All settings (paths, time zone, CSV format, manifest metadata) live here, in one place.
Paths are resolved relative to the project root, so the pipeline runs on any machine.
"""

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# config.py lives in <project>/src/, so the project root is one level above.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable settings for one pipeline run.

    main.py creates one instance and passes it to every step.
    Tests create their own instance with temporary folders, so they never touch real data.
    """

    # --- Input (Bronze) ---
    raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    customers_file: str = "raw_customers.csv"
    orders_file: str = "raw_orders.csv"

    # --- Output ---
    lakehouse_dir: Path = PROJECT_ROOT / "cdm_lakehouse"
    quarantine_dir: Path = PROJECT_ROOT / "data" / "quarantine"
    reports_dir: Path = PROJECT_ROOT / "reports"
    logs_dir: Path = PROJECT_ROOT / "logs"

    # --- Transformation ---
    # Applied to timestamps that carry no time zone (decision 1.3).
    default_timezone: str = "UTC"

    # --- CSV format (must match fileFormatSettings in model.json) ---
    csv_delimiter: str = ","
    csv_encoding: str = "utf-8"

    # --- Manifest metadata (from the assignment's reference model.json) ---
    manifest_name: str = "EnterpriseDataLake"
    manifest_description: str = "CDM Manifest for Ingested Customer and Sales Data"
    manifest_version: str = "1.0"

    def __post_init__(self) -> None:
        """Fail fast: reject an unknown time zone before any data is processed."""
        try:
            ZoneInfo(self.default_timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown time zone: {self.default_timezone!r}") from exc

    @property
    def customers_path(self) -> Path:
        """Full path to the raw customers file."""
        return self.raw_dir / self.customers_file

    @property
    def orders_path(self) -> Path:
        """Full path to the raw orders file."""
        return self.raw_dir / self.orders_file
