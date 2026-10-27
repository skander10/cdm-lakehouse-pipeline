"""Tests for the quality report: correct counts, no personal data, written safely."""

from pathlib import Path

from src.config import PipelineConfig
from src.extract import extract_customers, extract_orders
from src.load import quarantine_table
from src.quality import build_report, summary_rows, write_report
from src.transform import transform


# Helper: build the summary and the report from the real raw files, like the pipeline does.
def real_summary_and_report() -> tuple[list[list[str]], str]:
    config = PipelineConfig()
    customers = extract_customers(config)
    orders = extract_orders(config)
    result = transform(customers.data, orders.data, config.default_timezone)
    extract_rejected = {"Contact": customers.rejected, "SalesOrder": orders.rejected}
    quarantine = quarantine_table(extract_rejected, result.quarantined)
    summary = summary_rows(customers, orders, result)
    return summary, build_report(summary, quarantine, result.issues)


# The counts are right, and every line read is either written or quarantined (nothing lost).
def test_summary_counts_add_up() -> None:
    summary, _ = real_summary_and_report()

    assert summary == [
        ["Contact", "6", "4", "2", "3"],
        ["SalesOrder", "5", "4", "1", "0"],
    ]
    for _, lines_read, written, quarantined, _ in summary:
        assert int(lines_read) == int(written) + int(quarantined)


# The report names the problems by ID, but contains no names or e-mail addresses.
def test_report_contains_ids_but_no_personal_data() -> None:
    _, report = real_summary_and_report()

    assert "ORD-1005" in report
    assert "CST-003" in report
    assert "Charlie" not in report
    assert "@" not in report


# The report is written to reports/ and no temporary file is left behind.
def test_report_is_written(tmp_path: Path) -> None:
    config = PipelineConfig(reports_dir=tmp_path / "reports")

    path = write_report("# Data Quality Report\n", config)

    assert path == config.reports_dir / "data_quality_report.md"
    assert path.read_text() == "# Data Quality Report\n"
    assert list(tmp_path.rglob("*.tmp")) == []
