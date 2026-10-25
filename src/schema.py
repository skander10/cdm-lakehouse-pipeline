"""Target schema: the CDM entities Contact and SalesOrder and their relationship.

Single source of truth: the transformation, the CSV writer and the model.json generator
all read column names, data types and descriptions from here.
All values are taken from the assignment's reference model.json.
"""

from dataclasses import dataclass

# Data types used in the assignment's model.json.
CDM_DATA_TYPES = {"string", "dateTime", "decimal", "int64"}


@dataclass(frozen=True)
class Attribute:
    """One column of an entity."""

    name: str
    data_type: str
    description: str


@dataclass(frozen=True)
class Entity:
    """One CDM entity (a table) and the columns it contains, in order."""

    name: str
    description: str
    attributes: tuple[Attribute, ...]

    @property
    def column_names(self) -> list[str]:
        """Column names in the order they appear in the CSV file."""
        return [attribute.name for attribute in self.attributes]

    @property
    def location(self) -> str:
        """Path of the data file relative to model.json, e.g. 'Contact/Contact.csv'."""
        return f"{self.name}/{self.name}.csv"


@dataclass(frozen=True)
class Relationship:
    """A foreign key: from_entity.from_attribute points to to_entity.to_attribute."""

    name: str
    from_entity: str
    from_attribute: str
    to_entity: str
    to_attribute: str


CONTACT = Entity(
    name="Contact",
    description="Standard CDM Contact entity for individual customers",
    attributes=(
        Attribute("contactid", "string", "Unique primary key for the contact"),
        Attribute("firstname", "string", "First name of the contact"),
        Attribute("lastname", "string", "Last name of the contact"),
        Attribute("emailaddress1", "string", "Primary email address"),
        Attribute("createdon", "dateTime", "ISO 8601 creation timestamp"),
        Attribute("statecode", "int64", "Status code: 0 for Active, 1 for Inactive"),
    ),
)

SALES_ORDER = Entity(
    name="SalesOrder",
    description="Standard CDM SalesOrder entity for transactions",
    attributes=(
        Attribute("salesorderid", "string", "Unique order identifier"),
        Attribute("customerid", "string", "Foreign key reference to Contact"),
        Attribute("totalamount", "decimal", "Total order amount in USD"),
        Attribute("createdon", "dateTime", "ISO 8601 transaction timestamp"),
    ),
)

CONTACT_SALES_ORDER = Relationship(
    name="Contact_SalesOrder_Relationship",
    from_entity="SalesOrder",
    from_attribute="customerid",
    to_entity="Contact",
    to_attribute="contactid",
)

ENTITIES = (CONTACT, SALES_ORDER)
RELATIONSHIPS = (CONTACT_SALES_ORDER,)