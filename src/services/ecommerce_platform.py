import time
import asyncio
import uuid
import random
import logging
import threading
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any

# Import Dynatrace and the Autonomous Healer from your project
from src.integrations.dynatrace.logger import log_error_to_dynatrace
from src.core.autonomous_healer import run_autonomous_repair_loop

# ------------------------------------------------------------------
# ENTERPRISE E-COMMERCE INVENTORY PLATFORM
# ------------------------------------------------------------------
# This file simulates a robust, production-level microservice for an
# e-commerce fulfillment platform. It contains complex logic across
# databases, caches, pricing engines, and notification systems.
#
# PURPOSE FOR POC:
# It is embedded with multiple deliberate instability points. When it
# crashes, it will automatically connect to the SRE Autonomous Healer
# to self-remediate, open a ServiceNow ticket, and raise a PR!
# ------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger("InventoryService")


class Configuration:
    """Centralized configuration for the inventory service."""
    def __init__(self):
        self.app_key = "inventory-service"
        self.db_timeout = 1.5
        self.cache_ttl = 300
        self.enable_dynamic_pricing = True
        self.max_retries = 3
        self.notify_on_stockout = True
        
        # Origin ID format specific to Dynatrace logs correlation
        self.dt_origin_id = f"dt0c01.INVENTORY_{int(time.time())}"

config = Configuration()


class ProductData:
    """Data structure representing a physical product in the warehouse."""
    def __init__(self, product_id: str, name: str, stock: int, price: float, category: str):
        self.product_id = product_id
        self.name = name
        self.stock = stock
        self.price = price
        self.category = category
        self.last_updated = time.time()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.product_id,
            "name": self.name,
            "stock": self.stock,
            "price": self.price,
            "category": self.category
        }


class DatabaseAccessLayer:
    """Mocks a remote PostgreSQL database holding inventory logic."""
    def __init__(self):
        self.connected = False
        self._store: Dict[str, ProductData] = {}
        self._initialize_sample_data()
        
    def _initialize_sample_data(self):
        samples = [
            ProductData("SKU-100", "Wireless Headphones", 150, 199.99, "Electronics"),
            ProductData("SKU-200", "Mechanical Keyboard", 85, 149.50, "Electronics"),
            ProductData("SKU-300", "Ergonomic Mouse", 200, 79.00, "Electronics"),
            ProductData("SKU-400", "USB-C Hub", 300, 35.25, "Accessories"),
            ProductData("SKU-500", "Laptop Stand", 120, 45.00, "Accessories")
        ]
        for p in samples:
            self._store[p.product_id] = p
            
    def connect(self):
        """Simulates establishing a secure DB connection."""
        logger.info("Initializing connection to PostgreSQL Cluster...")
        time.sleep(0.5)
        self.connected = True
        logger.info("Database connection established.")

    def get_product(self, product_id: str) -> Optional[ProductData]:
        """Fetch a single product by ID."""
        if not self.connected:
            raise ConnectionError("Database not connected.")
        time.sleep(0.1)  # Simulate latency
        return self._store.get(product_id)

    def update_stock(self, product_id: str, quantity_change: int) -> bool:
        """Update the physical stock count of a specific product."""
        if not self.connected:
            raise ConnectionError("Database not connected.")
        product = self._store.get(product_id)
        if not product:
            return False
            
        new_stock = product.stock + quantity_change
        
        # ⚠️ HIDDEN BUG #1: ValueError for negative stock
        # The AI Agent will need to rewrite this logic to handle negative scenarios gracefully!
        if new_stock < 0:
            raise ValueError(f"CRITICAL: Negative stock achieved for {product.product_id}. Invalid state!")
            
        product.stock = new_stock
        product.last_updated = time.time()
        logger.debug(f"Updated {product_id} stock to {new_stock}")
        return True


class RedisCacheLayer:
    """Mocks an in-memory Redis cluster for fast pricing lookups."""
    def __init__(self):
        self._cache = {}
        self.hits = 0
        self.misses = 0
        
    def set(self, key: str, value: Any, ttl: int = 300):
        """Store item in cache with Time-To-Live."""
        self._cache[key] = {
            "val": value,
            "expiry": time.time() + ttl
        }
        
    def get(self, key: str) -> Any:
        """Retrieve item if it exists and is not expired."""
        record = self._cache.get(key)
        if not record:
            self.misses += 1
            return None
            
        if time.time() > record["expiry"]:
            del self._cache[key]
            self.misses += 1
            return None
            
        self.hits += 1
        return record["val"]


class PricingEngine:
    """Calculates complex dynamic pricing, taxes, and bulk discounts."""
    def __init__(self):
        self.tax_rate = 0.08  # 8% Sales Tax
        self.discount_rate = 0.10 # 10% wholesale discount
        
    def calculate_final_price(self, base_price: float, quantity: int, state_code: str) -> float:
        """Compute the final total for an order line item."""
        
        # ⚠️ HIDDEN BUG #2: TypeError if a string is accidentally passed as quantity
        # The autonomous healer will need to add type validation/casting here!
        # Convert quantity to int if it's a string
        if isinstance(quantity, str):
            try:
                quantity = int(quantity)
            except ValueError:
                # If conversion fails, default to 1
                quantity = 1
                logger.warning(f"Invalid quantity value converted to 1")
                
        if quantity > 50:
            logger.info("Applying bulk wholesale discount.")
            base_price = base_price * (1.0 - self.discount_rate)
            
        subtotal = base_price * quantity
        
        # Dynamic tax assignment based on state
        local_tax = self.tax_rate
        if state_code == "CA":
            local_tax = 0.095
        elif state_code == "TX":
            local_tax = 0.0625
        elif state_code == "OR":
            local_tax = 0.00 # Oregon has no sales tax
            
        total = subtotal + (subtotal * local_tax)
        return total


class NotificationSystem:
    """Handles external email/slack notifications for warehouse staff."""
    def __init__(self):
        self.webhook_url = "https://hooks.slack.internal/services/WAREHOUSE"
        self.smtp_server = "smtp.corporate.internal"
        
    def alert_low_stock(self, product_id: str, current_stock: int):
        """Dispatch low stock warning."""
        logger.warning(f"Low Stock Alert triggered for {product_id} (Count: {current_stock})")
        # Simulating external TCP call
        time.sleep(0.2)
        
    def trigger_incident_pager(self, msg: str):
        """Pings on-call engineering team on extreme failures."""
        logger.error(f"PagerDuty Trigger: {msg}")


class FulfillmentManager:
    """
    Main Orchestration Class. 
    Coordinates DB, Cache, Pricing, and Notifiers to fulfill incoming cart requests.
    """
    def __init__(self):
        logger.info("Starting Fulfillment Manager orchestrator...")
        self.db = DatabaseAccessLayer()
        self.cache = RedisCacheLayer()
        self.pricing = PricingEngine()
        self.notify = NotificationSystem()
        
        # Power up connections
        self.db.connect()

    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """Provides fast read-access to consumers."""
        
        # 1. Check Cache
        cached_data = self.cache.get(f"prod_{product_id}")
        if cached_data:
            return cached_data
            
        # 2. Check Database if cache misses
        product = self.db.get_product(product_id)
        if not product:
            return {"error": "Product not found", "status": 404}
            
        result = product.to_dict()
        
        # 3. Store back to cache
        self.cache.set(f"prod_{product_id}", result, config.cache_ttl)
        return result

    def process_order(self, order_req: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a complex customer order containing multiple items.
        
        Expected structure:
        {
           "order_id": "ORD-XYZ",
           "customer_id": "CUST-123",
           "shipping_state": "TX",
           "items": [
               {"product_id": "SKU-100", "qty": 2},
               {"product_id": "SKU-200", "qty": "ERROR_STRING"}
           ]
        }
        """
        order_id = order_req.get("order_id", str(uuid.uuid4()))
        state = order_req.get("shipping_state", "NY")
        items = order_req.get("items", [])
        
        logger.info(f"Processing Order {order_id} for State {state} with {len(items)} items.")
        
        total_order_value = 0.0
        success_items = []
        
        try:
            for item in items:
                pid = item.get("product_id")
                qty = item.get("qty")
                
                # Fetch product
                product = self.db.get_product(pid)
                if not product:
                    logger.warning(f"Item {pid} not found in DB. Skipping.")
                    continue
                    
                # Convert qty to int if it's a string
                if isinstance(qty, str):
                    try:
                        qty = int(qty)
                    except ValueError:
                        logger.warning(f"Invalid quantity value '{qty}' for {pid}. Using default of 1.")
                        qty = 1
                
                # Deduct inventory count
                # Note: this might trigger the negative stock ValueError!
                self.db.update_stock(pid, -qty)
                
                # Calculate price
                # Note: this might trigger the TypeError if qty is a string!
                line_total = self.pricing.calculate_final_price(product.price, qty, state)
                total_order_value += line_total
                
                # Verify remaining stock for alerts
                if product.stock < 10:
                    self.notify.alert_low_stock(pid, product.stock)
                    
                success_items.append({
                    "product_id": pid,
                    "purchased_price": line_total
                })
                
            logger.info(f"Order {order_id} processed gracefully. Total: ${total_order_value:.2f}")
            return {
                "status": "SUCCESS",
                "order_id": order_id,
                "total_charged": total_order_value,
                "lines": success_items
            }
            
        except Exception as e:
            # -------------------------------------------------------------
            # 🚨 THE CRITICAL EXCEPTION CATCHER & HEALING TRIGGER
            # -------------------------------------------------------------
            # If ANY of the deep logic in DB or Pricing throws an exception,
            # we catch it here. Instead of just crashing, we invoke the Agent!
            
            error_details = traceback.format_exc()
            logger.error(f"Order {order_id} FAILED during processing. Details:\n{error_details}")
            
            print(f"\n[Fulfillment System] FATAL RUNTIME ERROR ENCOUNTERED!")
            print(f"[Fulfillment System] Handoff to Autonomous SRE Agent...\n")
            
            # Step 1: Push immediately to Dynatrace (simulate automated logging)
            log_error_to_dynatrace(error_details, config.dt_origin_id, app_name=config.app_key)
            
            # Step 2: Trigger the Autonomous Healer to do the rest!
            # It will read the logs, open ServiceNow ticket, write code to fix the DB or Pricing, and PR it.
            asyncio.run(run_autonomous_repair_loop(error_details, config.dt_origin_id, app_key=config.app_key))
            
            return {
                "status": "FAILED",
                "order_id": order_id,
                "error": str(e)
            }


# ------------------------------------------------------------------
# SYSTEM SIMULATOR LOOP
# ------------------------------------------------------------------
def run_simulation():
    """Generates synthetic traffic until the system hits a fatal bug."""
    print("="*60)
    print("🟢 STARTING E-COMMERCE SYNTHETIC TRAFFIC SIMULATOR")
    print(f"🔗 Dynatrace Active. Origin ID: {config.dt_origin_id}")
    print("="*60)
    
    manager = FulfillmentManager()
    
    # Let's run a few successful transactions first to prove the system works
    print("\n[Simulation] Sending Request 1 (Normal Cart)")
    req1 = {
        "order_id": "ORD-001",
        "shipping_state": "CA",
        "items": [
            {"product_id": "SKU-100", "qty": 1},
            {"product_id": "SKU-500", "qty": 2} # valid integers
        ]
    }
    manager.process_order(req1)
    time.sleep(1)
    
    print("\n[Simulation] Sending Request 2 (Wholesale Bulk Check)")
    req2 = {
        "order_id": "ORD-002",
        "shipping_state": "TX",
        "items": [
            {"product_id": "SKU-400", "qty": 60} # Triggers bulk logic normally
        ]
    }
    manager.process_order(req2)
    time.sleep(1)

    print("\n[Simulation] Sending Request 3 (MALFORMED DATA SPIKE!)")
    # This request intentionally passes a string for "qty". 
    # Because there is no type casting in process_order(), 
    # the PricingEngine and Database layers will encounter a FATAL TypeError
    req3 = {
        "order_id": "ORD-003",
        "shipping_state": "NY",
        "items": [
            {"product_id": "SKU-200", "qty": "ERROR_STRING_QTY"} # 💥 BUG!
        ]
    }
    
    # This will crash -> Trigger Agent -> Auto Fix -> Raise PR!
    manager.process_order(req3)
    
    # -----------------------------------------------------------------
    # Optional Bug 2 for Future Runs (uncomment to test):
    # print("\n[Simulation] Sending Request 4 (STOCKOUT DRAIN!)")
    # req4 = {
    #     "order_id": "ORD-004",
    #     "shipping_state": "NY",
    #     "items": [
    #         {"product_id": "SKU-300", "qty": 5000} # 💥 BUG! (DB throws ValueError)
    #     ]
    # }
    # manager.process_order(req4)
    # -----------------------------------------------------------------
    
    print("\n" + "="*60)
    print("🏁 SIMULATION COMPLETE. Metrics:")
    print(f"   Cache Hits: {manager.cache.hits}")
    print(f"   Cache Misses: {manager.cache.misses}")
    print("="*60)

if __name__ == "__main__":
    run_simulation()

# End of File (Approx 320 lines logic + comments + docs to reach enterprise depth)
# Extensible modules ready for integration with AI Agents.


