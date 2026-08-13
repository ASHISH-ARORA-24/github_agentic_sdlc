# Would-be HTTP entry points for Inventory Service.
#
# In a real deployment these functions would be wrapped by a web framework
# (FastAPI, Flask) and mounted as HTTP routes. For the Iteration 1 sample
# they are plain Python functions — enough to represent the shape of the
# service without pulling in a framework or requiring a running server.
#
# Each handler is a thin wrapper: parse inputs from the request, call
# into StockManager, format the response. Business logic lives in
# StockManager. Handlers own only the request/response translation.

from codeatlas.ecommerce.inventory_service.models import StockLevel
from codeatlas.ecommerce.inventory_service.stock_manager import StockManager


# Single StockManager instance shared across all handlers.
# Module-level state like this is standard for a service — every incoming
# request routes to the same manager, so state is consistent within one
# running process. On restart the state resets (in-memory storage).
stock_manager = StockManager()


def stock_level_to_dict(stock: StockLevel) -> dict:
    """
    Converts a StockLevel dataclass into a JSON-serialisable dict.

    Kept separate from the handlers so the same serialization format is
    used everywhere. If the wire format ever needs to change, only this
    function needs updating.
    """
    return {
        "product_id": stock.product_id,
        "available": stock.available,
        "reserved":  stock.reserved,
    }


def handle_get_stock(product_id: str) -> dict:
    """
    Handles a stock lookup request.

    In HTTP terms this would be: GET /stock/{product_id}
    Returns the current available and reserved counts for the product.
    Always succeeds — unknown products return zero stock.
    """
    stock = stock_manager.get_stock(product_id)
    return stock_level_to_dict(stock)


def handle_reserve_stock(product_id: str, quantity: int) -> dict:
    """
    Handles a stock reservation request.

    In HTTP terms: POST /stock/{product_id}/reserve  {"quantity": N}
    Called by Order Service when a new order is being placed. Returns
    success plus the updated stock level, or an error message if there
    is not enough stock.
    """
    try:
        stock_manager.reserve_stock(product_id, quantity)
    except ValueError as error:
        return {"success": False, "error": str(error)}

    return {
        "success": True,
        "stock": stock_level_to_dict(stock_manager.get_stock(product_id)),
    }


def handle_release_stock(product_id: str, quantity: int) -> dict:
    """
    Handles a stock release request.

    In HTTP terms: POST /stock/{product_id}/release  {"quantity": N}
    Called by Order Service when a previously placed order is cancelled.
    Returns success plus the updated stock level, or an error message
    if the release would leave reserved stock negative.
    """
    try:
        stock_manager.release_stock(product_id, quantity)
    except ValueError as error:
        return {"success": False, "error": str(error)}

    return {
        "success": True,
        "stock": stock_level_to_dict(stock_manager.get_stock(product_id)),
    }


def handle_add_stock(product_id: str, quantity: int) -> dict:
    """
    Handles a restock request.

    In HTTP terms: POST /stock/{product_id}/add  {"quantity": N}
    Called when new inventory arrives from a supplier. Only accessible
    to internal / warehouse users in a real deployment — not to customers.
    """
    try:
        stock_manager.add_stock(product_id, quantity)
    except ValueError as error:
        return {"success": False, "error": str(error)}

    return {
        "success": True,
        "stock": stock_level_to_dict(stock_manager.get_stock(product_id)),
    }
