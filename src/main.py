"""Main: run the whole pipeline with one command:  python -m src.main

extract -> transform -> load -> manifest. Each step lives in its own module;
this file only calls them in the right order.
"""

import logging

from src.config import PipelineConfig
from src.extract import extract_customers, extract_orders
from src.load import quarantine_table, write_cdm_tables, write_quarantine
from src.logging_config import setup_logging
from src.manifest import build_manifest, check_manifest, write_manifest
from src.transform import transform

logger = logging.getLogger(__name__)


# Run the whole pipeline once. Without a config, the normal settings are used;
# a test can pass its own config to write into an empty test folder.
def main(config: PipelineConfig | None = None) -> None:
    config = config or PipelineConfig()

    # Part 1: start logging (console + logs/pipeline.log), before any other step
    log_file = setup_logging(config.logs_dir)
    logger.info("Pipeline started (log file: %s)", log_file.name)

    # Part 2: extract (read the raw files) and transform (clean them into the CDM tables)
    customers = extract_customers(config)
    orders = extract_orders(config)
    result = transform(customers.data, orders.data, config.default_timezone)

    # Part 3: load (write the CDM tables and one quarantine file for extract + transform)
    write_cdm_tables(result.contacts, result.sales_orders, config)
    extract_rejected = {"Contact": customers.rejected, "SalesOrder": orders.rejected}
    write_quarantine(quarantine_table(extract_rejected, result.quarantined), config)

    # Part 4: manifest (build model.json, check it against the CSV files, then write it)
    manifest = build_manifest(config)
    check_manifest(manifest, config)
    write_manifest(manifest, config)

    # Part 5: summary of the run (counts only, no personal data)
    quarantined = len(customers.rejected) + len(orders.rejected) + len(result.quarantined)
    logger.info(
        "Pipeline finished: %d contacts and %d sales orders written, %d quarantined, %d issues",
        len(result.contacts),
        len(result.sales_orders),
        quarantined,
        len(result.issues),
    )


if __name__ == "__main__":
    main()
