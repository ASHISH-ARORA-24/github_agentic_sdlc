# Core business logic for Inventory Service.
#
# StockManager is the single point where stock state changes happen.
# All reservations, releases, and restocks go through this class so that
# stock invariants are enforced in exactly one place.
#
# Storage is an in-memory dict for the Iteration 1 sample. Swapping to a
# database later means changing only this file — the public method
# signatures stay identical, so main.py and any callers do not change.

from models import StockLevel


# Minimum allowed quantity for any stock operation.
# Zero or negative quantities are nonsensical — reserving 0 units is a no-op
# and reserving -1 units would silently increase available stock.
MIN_QUANTITY = 1


class StockManager:
    """
    Manages stock levels for all products.

    Keeps stock in an in-memory dict keyed by product_id. Provides the
    four operations that stock ever needs to undergo: query, reserve
    (for a pending order), release (undo a reservation), and add (restock).

    Every state-changing method validates its inputs first. Invalid input
    raises ValueError with a message explaining what was wrong — callers
    can catch this and return a 400 response to the client.
    """

    def __init__(self) -> None:
        """
        Initialises an empty stock ledger.

        A production version would load stock from a database at startup.
        In-memory storage means stock resets every time the service restarts —
        acceptable for a sample, unacceptable for real inventory.
        """
        self._stock: dict[str, StockLevel] = {}

    def _ensure_product_exists(self, product_id: str) -> None:
        """
        Creates an empty StockLevel for a product if one does not exist.

        Used internally before any state change. Auto-creating on first
        touch means callers do not need to explicitly register a product
        before adding stock to it — the first add_stock call sets it up.
        """
        if product_id not in self._stock:
            self._stock[product_id] = StockLevel(
                product_id=product_id,
                available=0,
                reserved=0,
            )

    def _validate_quantity(self, quantity: int) -> None:
        """
        Rejects zero or negative quantities.

        Split into its own method so the same validation is applied
        identically across reserve, release, and add — one rule, one place.
        """
        if quantity < MIN_QUANTITY:
            raise ValueError(f"Quantity must be at least {MIN_QUANTITY}, got {quantity}")

    def get_stock(self, product_id: str) -> StockLevel:
        """
        Returns the current stock level for a product.

        If the product has never been seen before, returns a zero-stock
        StockLevel rather than raising. This makes get_stock safe to call
        for any product_id — the caller does not need to know whether the
        product is registered.
        """
        self._ensure_product_exists(product_id)
        return self._stock[product_id]

    def has_sufficient_stock(self, product_id: str, quantity: int) -> bool:
        """
        Checks whether a product has at least quantity units available.

        This is a pure query — it never mutates state. Split from
        reserve_stock so callers can check availability before deciding
        to reserve, and so reserve_stock itself can validate defensively.
        """
        self._validate_quantity(quantity)
        stock = self.get_stock(product_id)
        return stock.available >= quantity

    def reserve_stock(self, product_id: str, quantity: int) -> None:
        """
        Moves N units from available into reserved.

        Called when an order is being created — the units are held for
        that order and are no longer available to anyone else. If the
        product does not have enough available stock, raises ValueError.

        The defensive check inside this method (rather than trusting the
        caller to have called has_sufficient_stock first) prevents race
        conditions and protects the invariant that reserved units always
        exist in available first.
        """
        self._validate_quantity(quantity)

        if not self.has_sufficient_stock(product_id, quantity):
            available = self.get_stock(product_id).available
            raise ValueError(
                f"Not enough stock for {product_id}: requested {quantity}, available {available}"
            )

        stock = self._stock[product_id]
        stock.available -= quantity
        stock.reserved  += quantity

    def release_stock(self, product_id: str, quantity: int) -> None:
        """
        Moves N units from reserved back into available.

        Called when an order is cancelled — the previously reserved units
        return to the pool so other orders can claim them. Raises ValueError
        if there are not enough reserved units to release (which would
        indicate a bug in the caller — releasing what was never reserved).
        """
        self._validate_quantity(quantity)
        self._ensure_product_exists(product_id)

        stock = self._stock[product_id]
        if stock.reserved < quantity:
            raise ValueError(
                f"Cannot release {quantity} units of {product_id}: only {stock.reserved} reserved"
            )

        stock.reserved  -= quantity
        stock.available += quantity

    def add_stock(self, product_id: str, quantity: int) -> None:
        """
        Adds N units to available stock.

        Called when new inventory arrives — for example a supplier delivery.
        Only increments available; never touches reserved because incoming
        stock has not been claimed by any order yet.
        """
        self._validate_quantity(quantity)
        self._ensure_product_exists(product_id)

        self._stock[product_id].available += quantity
