# inventory_service

Owns product stock levels. The single source of truth for how many units of any product are available.

## What this folder contains

- `models.py` — `Product` and `StockLevel` dataclasses
- `stock_manager.py` — `StockManager` class with the core business logic (reserve, release, add, query)
- `main.py` — would-be HTTP handlers (plain functions that route incoming requests to `StockManager`)

## Why this exists

Stock is a piece of state that must not be duplicated. If two services both tracked stock counts they would drift out of sync — an order could be placed against stock that no longer exists. Isolating stock in one service means every stock change goes through one place and is always consistent.

## Operations exposed

| Operation | Purpose |
|---|---|
| `get_stock(product_id)` | Read current available and reserved counts |
| `reserve_stock(product_id, quantity)` | Hold N units for a pending order — decrements available, increments reserved |
| `release_stock(product_id, quantity)` | Undo a reservation — increments available, decrements reserved (used on order cancel) |
| `add_stock(product_id, quantity)` | Restock — increments available |

## How it fits into the larger system

Inventory Service is a **dependency** — it does not call any other service. It only receives calls. Order Service is the primary caller, invoking `reserve_stock` when an order is created and `release_stock` when an order is cancelled.

## Data storage

In-memory Python dict keyed by `product_id`. Real deployment would swap this for a database — the `StockManager` class hides that choice from the rest of the codebase, so swapping storage does not change the public API.
