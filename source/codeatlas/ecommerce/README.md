# ecommerce

A two-service sample project for CodeAtlas — models a small slice of an e-commerce backend split across two microservices.

## What this folder contains

Two independent services, each in its own subfolder:

- `inventory_service/` — owns product stock levels
- `order_service/` — owns customer orders

Each service is a self-contained Python package with its own models, business logic, and would-be HTTP handlers.

## Why this exists

CodeAtlas is designed around a three-level structure — `owner/project/repo` — so it can answer questions that span multiple repos in the same project. The single-repo `grade_calculator` sample cannot exercise that. This sample can.

Concretely, indexing this project lets us test:

- Within-service questions — *"how does StockManager reserve stock?"*
- Cross-service questions — *"what does Order Service call in Inventory Service?"*
- Structural questions — *"which service owns the source of truth for stock?"*

## How the two services relate

The services are independent — they run in separate processes, own separate data, and only talk over HTTP. Order Service depends on Inventory Service; Inventory Service knows nothing about orders.

```
[ Order Service ]  ──HTTP──▶  [ Inventory Service ]
    creates orders                owns stock levels
```

- On `create_order` — Order Service calls Inventory Service to reserve stock. If stock is available it is decremented; the order is then created.
- On `cancel_order` — Order Service calls Inventory Service to release the previously reserved stock.

## Not actually running

The code is written as if these were real HTTP services, but no server is ever started. Order Service's `inventory_client.py` builds and shows the HTTP calls it would make — enough to be realistic code for CodeAtlas to index, without needing a web framework or two running processes.

Running the services for real is an Iteration 3 concern, not Iteration 1.

## Known limitation this sample exposes

The AST crawler can trace function calls *within* a service perfectly. It cannot trace HTTP calls *across* services — those go over the network, not through Python imports. This is a real limitation of static code analysis on microservices. When we index this sample, cross-service Q&A will have to rely on ChromaDB's semantic search of code and docstrings, not the Neo4j call graph.
