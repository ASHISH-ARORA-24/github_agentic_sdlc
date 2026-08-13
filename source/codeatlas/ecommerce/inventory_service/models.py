# Data models for Inventory Service.
#
# These are plain data holders — no business logic. Keeping them separate
# from stock_manager.py means the shape of the data can be understood
# without reading any logic, and the logic can be understood without
# worrying about serialization details.
#
# Using @dataclass because it produces clean type-hinted classes that
# CodeAtlas can parse into meaningful graph nodes and embed as chunks
# with all their field names and types intact.

from dataclasses import dataclass


@dataclass
class Product:
    """
    A product that can be sold and stocked.

    This is the identity of a product — its ID, human-readable name, and
    price. Stock quantities are tracked separately in StockLevel because
    quantities change constantly while the product identity itself is stable.

    price_cents is stored as an integer number of cents rather than a
    float dollar amount. Floats introduce rounding errors in financial
    math — every serious payment system uses integer smallest-units.
    """

    product_id: str
    name: str
    price_cents: int


@dataclass
class StockLevel:
    """
    The current stock state for a single product.

    Splits total stock into two buckets:
    - available: units that can be reserved by new orders
    - reserved: units already held by pending orders

    The sum (available + reserved) is the total physical stock. Splitting
    into two counters prevents overselling — an order that has reserved
    stock but not yet paid does not appear as available to other orders,
    but is still counted as physically present.
    """

    product_id: str
    available: int
    reserved: int
