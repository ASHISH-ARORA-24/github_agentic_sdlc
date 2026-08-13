# Tests for StockManager.
#
# These tests verify the core stock management logic —
# reserve, release, add, and validation.

import pytest
import sys
from pathlib import Path

# Add the inventory_service folder to path so we can import its modules directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_manager import StockManager


def test_add_stock_increases_available():
    """Adding stock increases the available count."""
    manager = StockManager()
    manager.add_stock("product-1", 10)
    assert manager.get_stock("product-1").available == 10


def test_reserve_stock_moves_available_to_reserved():
    """Reserving stock decrements available and increments reserved."""
    manager = StockManager()
    manager.add_stock("product-1", 10)
    manager.reserve_stock("product-1", 3)
    stock = manager.get_stock("product-1")
    assert stock.available == 7
    assert stock.reserved == 3


def test_reserve_stock_fails_when_insufficient():
    """Reserving more than available raises ValueError."""
    manager = StockManager()
    manager.add_stock("product-1", 5)
    with pytest.raises(ValueError):
        manager.reserve_stock("product-1", 10)


def test_release_stock_moves_reserved_back_to_available():
    """Releasing reserved stock returns it to available."""
    manager = StockManager()
    manager.add_stock("product-1", 10)
    manager.reserve_stock("product-1", 4)
    manager.release_stock("product-1", 4)
    stock = manager.get_stock("product-1")
    assert stock.available == 10
    assert stock.reserved == 0


def test_invalid_quantity_raises_value_error():
    """Zero or negative quantity raises ValueError."""
    manager = StockManager()
    with pytest.raises(ValueError):
        manager.add_stock("product-1", 0)
    with pytest.raises(ValueError):
        manager.add_stock("product-1", -1)
