"""Transform: turn the raw tables into the CDM tables Contact and SalesOrder (assignment Step 1).

Uses the tools from validators.py on every row and decides what happens with each problem:
- required value missing or invalid  -> the record goes to the quarantine
- optional value missing or invalid  -> the value is left empty and a warning is logged
Log messages contain record IDs only, never names or e-mail addresses.
"""

import logging
from dataclasses import dataclass

import pandas as pd

from src.schema import CONTACT, SALES_ORDER
from src.validators import (
    normalize_email,
    normalize_status,
    parse_amount,
    parse_timestamp,
    split_name,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Part 1: the result packages
# ---------------------------------------------------------------------------


# A data problem that did not stop the record (value left empty, or an assumption was made).
@dataclass
class DataIssue:
    entity: str  # "Contact" or "SalesOrder"
    record_id: str
    field: str
    message: str


# A record that was not accepted: the reason, plus the raw values for a person to check.
@dataclass
class QuarantinedRecord:
    entity: str
    record_id: str
    reason: str
    values: dict[str, str]


# Everything transform hands over to the next steps.
@dataclass
class TransformResult:
    contacts: pd.DataFrame
    sales_orders: pd.DataFrame
    quarantined: list[QuarantinedRecord]
    issues: list[DataIssue]

    # ---------------------------------------------------------------------------


# Part 2: small helpers (record a problem + log it, IDs only)
# ---------------------------------------------------------------------------


# Put a record into the quarantine and log a warning.
def quarantine(
    quarantined: list[QuarantinedRecord],
    entity: str,
    record_id: str,
    reason: str,
    values: dict[str, str],
) -> None:
    quarantined.append(QuarantinedRecord(entity, record_id, reason, values))
    logger.warning("%s %s: quarantined (%s)", entity, record_id or "<no id>", reason)


# Record a data issue and log a warning.
def report_issue(
    issues: list[DataIssue], entity: str, record_id: str, field: str, message: str
) -> None:
    issues.append(DataIssue(entity, record_id, field, message))
    logger.warning("%s %s: %s %s", entity, record_id, field, message)


# Describe why a raw value could not be used: it was empty, or it was there but invalid.
def missing_or_invalid(raw: str) -> str:
    return "missing" if not raw.strip() else "invalid"


# Check a required ID: returns the reason if it is missing or a duplicate, otherwise None.
def check_id(record_id: str, seen_ids: set[str]) -> str | None:
    if not record_id:
        return "id is missing"
    if record_id in seen_ids:
        return "duplicate id"
    return None


# ---------------------------------------------------------------------------
# Part 3: Contact
# ---------------------------------------------------------------------------


# Build the Contact table from the raw customers.
def transform_contacts(
    raw: pd.DataFrame,
    default_timezone: str,
    quarantined: list[QuarantinedRecord],
    issues: list[DataIssue],
) -> pd.DataFrame:
    """Map raw customers to the CDM Contact entity (assignment Step 1, Contact)."""
    rows = []
    seen_ids: set[str] = set()

    for record in raw.to_dict("records"):
        contact_id = record["cust_id"].strip()

        # Required: contactid must be present and unique
        reason = check_id(contact_id, seen_ids)
        if reason:
            quarantine(quarantined, "Contact", contact_id, reason, record)
            continue
        seen_ids.add(contact_id)

        # Optional: name
        first_name, last_name = split_name(record["full_name"])
        if first_name is None:
            report_issue(
                issues, "Contact", contact_id, "firstname, lastname", "missing, both left empty"
            )
        elif last_name is None:
            report_issue(
                issues, "Contact", contact_id, "lastname", "only one name part, left empty"
            )

        # Optional: e-mail (assignment: invalid format -> logged and set to null)
        email = normalize_email(record["email_addr"])
        if email is None:
            problem = missing_or_invalid(record["email_addr"])
            report_issue(issues, "Contact", contact_id, "emailaddress1", f"{problem}, set to null")

        # Optional: creation date (assignment: ISO 8601 UTC)
        created_on, timezone_assumed = parse_timestamp(record["signup_date"], default_timezone)
        if created_on is None:
            problem = missing_or_invalid(record["signup_date"])
            report_issue(issues, "Contact", contact_id, "createdon", f"{problem}, left empty")
        elif timezone_assumed:
            message = f"no time zone given, {default_timezone} assumed"
            report_issue(issues, "Contact", contact_id, "createdon", message)

        # Optional: status (assignment: active -> 0, inactive -> 1)
        statecode = normalize_status(record["user_status"])
        if statecode is None:
            problem = missing_or_invalid(record["user_status"])
            report_issue(issues, "Contact", contact_id, "statecode", f"{problem}, left empty")

        rows.append(
            {
                "contactid": contact_id,
                "firstname": first_name,
                "lastname": last_name,
                "emailaddress1": email,
                "createdon": created_on,
                "statecode": statecode,
            }
        )

    logger.info("Contact: %d records transformed", len(rows))
    return pd.DataFrame(rows, columns=CONTACT.column_names, dtype=object)


# ---------------------------------------------------------------------------
# Part 4: SalesOrder
# ---------------------------------------------------------------------------


# Build the SalesOrder table from the raw orders; orders of unknown customers are quarantined.
def transform_sales_orders(
    raw: pd.DataFrame,
    contact_ids: set[str],
    default_timezone: str,
    quarantined: list[QuarantinedRecord],
    issues: list[DataIssue],
) -> pd.DataFrame:
    """Map raw orders to the CDM SalesOrder entity (assignment Step 1, SalesOrder)."""
    rows = []
    seen_ids: set[str] = set()

    for record in raw.to_dict("records"):
        order_id = record["tx_id"].strip()

        # Required: salesorderid must be present and unique
        reason = check_id(order_id, seen_ids)
        if reason:
            quarantine(quarantined, "SalesOrder", order_id, reason, record)
            continue
        seen_ids.add(order_id)

        # Required: customerid must be present and the customer must exist (orphan check)
        customer_id = record["customer_id"].strip()
        if not customer_id:
            quarantine(quarantined, "SalesOrder", order_id, "customerid is missing", record)
            continue
        if customer_id not in contact_ids:
            reason = f"orphan: customer {customer_id} does not exist"
            quarantine(quarantined, "SalesOrder", order_id, reason, record)
            continue

        # Required: totalamount must be a valid number
        amount = parse_amount(record["amount_usd"])
        if amount is None:
            reason = f"totalamount {missing_or_invalid(record['amount_usd'])}"
            quarantine(quarantined, "SalesOrder", order_id, reason, record)
            continue

        # Accepted, but flagged: negative amount (possible credit note)
        if amount < 0:
            message = "negative amount (possible credit note)"
            report_issue(issues, "SalesOrder", order_id, "totalamount", message)

        # Optional: creation date (assignment: ISO 8601 UTC)
        created_on, timezone_assumed = parse_timestamp(record["tx_timestamp"], default_timezone)
        if created_on is None:
            problem = missing_or_invalid(record["tx_timestamp"])
            report_issue(issues, "SalesOrder", order_id, "createdon", f"{problem}, left empty")
        elif timezone_assumed:
            message = f"no time zone given, {default_timezone} assumed"
            report_issue(issues, "SalesOrder", order_id, "createdon", message)

        rows.append(
            {
                "salesorderid": order_id,
                "customerid": customer_id,
                "totalamount": amount,
                "createdon": created_on,
            }
        )

    logger.info("SalesOrder: %d records transformed", len(rows))
    return pd.DataFrame(rows, columns=SALES_ORDER.column_names, dtype=object)


# ---------------------------------------------------------------------------
# Part 5: entry point
# ---------------------------------------------------------------------------


# Transform both tables: Contact first, because SalesOrder needs the list of valid contacts.
def transform(
    raw_customers: pd.DataFrame, raw_orders: pd.DataFrame, default_timezone: str
) -> TransformResult:
    """Run the transformation for Contact and SalesOrder."""
    quarantined: list[QuarantinedRecord] = []
    issues: list[DataIssue] = []

    contacts = transform_contacts(raw_customers, default_timezone, quarantined, issues)
    contact_ids = set(contacts["contactid"])
    sales_orders = transform_sales_orders(
        raw_orders, contact_ids, default_timezone, quarantined, issues
    )
    return TransformResult(contacts, sales_orders, quarantined, issues)
