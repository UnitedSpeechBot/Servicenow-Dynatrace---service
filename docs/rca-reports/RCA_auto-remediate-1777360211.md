Autonomous SRE Agent detected errors across multiple services.

Files patched: 

Error summary (truncated):
[ERROR][dt0c01.TEST_LIVE_123] TEST ERROR: Live ingestion successful using Classic dt0c01 token!
[ERROR][dt0c01.FULL_SCAN_1777290091] [ERROR][dt0c01.TEST_LIVE_123] TEST ERROR: Live ingestion successful using Classic dt0c01 token!

--- LIVE RUNTIME OUTPUT FROM src/services/ecommerce_platform.py ---
Traceback (most recent call last):
  File "src/services/ecommerce_platform.py", line 1, in <module>
============================================================
🟢 STARTING E-COMMERCE SYNTHETIC TRAFFIC SIMULATOR
🔗 Dynatrace Active. Origin ID: dt0c01.INVENTORY_1777289988
============================================================
2026-04-27 17:09:48,644 | INFO | InventoryService | Starting Fulfillment Manager orchestrator...
2026-04-27 17:09:48,645 | INFO | InventoryService | Initializing connection to PostgreSQL Cluster...
2026-04-27 17:09:49,149 | INFO | InventoryService | Database connection established.

[Simulation] Sending Request 1 (Normal Cart)
2026-04-27 17:09:49,149 | INFO | InventoryService | Processing Order ORD-001 for State CA with 2 items.
2026-04-27 17:09:49,354 | INFO | InventoryService | Order ORD-001 processed gracefully. Total: $317.54

[Simulation] Sending Request 2 (Wholesale Bulk Check)
2026-04-27 17:09:50,358 | INFO | InventoryService | Processing Order ORD-002 for State TX with 1 items.
2026-04-27 17:09:50,462 | INFO | InventoryService | Applying bulk wholesale discount.
2026-04-27 17:09:50,463 | INFO | InventoryService | Order ORD-002 processed gracefully. To