"""Tests for the target schema: it must match the assignment exactly."""

from src.schema import CDM_DATA_TYPES, CONTACT, ENTITIES, RELATIONSHIPS, SALES_ORDER


def test_contact_columns_match_assignment() -> None:
    assert CONTACT.column_names == [
        "contactid",
        "firstname",
        "lastname",
        "emailaddress1",
        "createdon",
        "statecode",
    ]


def test_sales_order_columns_match_assignment() -> None:
    assert SALES_ORDER.column_names == ["salesorderid", "customerid", "totalamount", "createdon"]


def test_file_locations_match_assignment() -> None:
    assert CONTACT.location == "Contact/Contact.csv"
    assert SALES_ORDER.location == "SalesOrder/SalesOrder.csv"


def test_all_data_types_are_cdm_types() -> None:
    for entity in ENTITIES:
        for attribute in entity.attributes:
            assert attribute.data_type in CDM_DATA_TYPES


def test_relationship_points_to_existing_columns() -> None:
    entities_by_name = {entity.name: entity for entity in ENTITIES}
    for relationship in RELATIONSHIPS:
        from_entity = entities_by_name[relationship.from_entity]
        to_entity = entities_by_name[relationship.to_entity]
        assert relationship.from_attribute in from_entity.column_names
        assert relationship.to_attribute in to_entity.column_names