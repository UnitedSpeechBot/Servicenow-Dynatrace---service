import time
import asyncio
import uuid
import random
import logging
from typing import Dict, Optional
from src.integrations.dynatrace.logger import log_error_to_dynatrace

# Setup basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class InventoryService:
    """
    E-Commerce Inventory Management Service.
    Handles stock updates, order processing, and fulfillment.
    """

    def __init__(self, origin_id: str = "dt0c01.AUTO_GENERATED"):
        self.origin_id = origin_id
        self.db = MockDatabase()
        self.tax_rates = {
            "CA": 0.0725,  # California
            "NY": 0.045,   # New York
            "TX": 0.0625,  # Texas
            "FL": 0.06,    # Florida
            "WA": 0.065,   # Washington
        }
        self.default_tax = 0.05  # 5% default

    def process_order(self, order_id: str, state: str, items: list):
        """
        Process an e-commerce order with multiple items.
        Updates inventory and calculates tax based on state.
        """
        logging.info(f"Processing Order {order_id} for State {state} with {len(items)} items.")
        
        total = 0.0
        tax_rate = self.tax_rates.get(state, self.default_tax)
        
        try:
            # Process each item in the order
            for item in items:
                pid = item.get("product_id")
                qty = item.get("quantity")
                
                # Convert string quantity to integer
                if isinstance(qty, str):
                    qty = int(qty)
                
                # Check if this is a wholesale order
                if qty > 10:
                    logging.info("Applying bulk wholesale discount.")
                
                # Get current price from "database"
                price = self.db.get_product_price(pid)
                
                # Calculate line total
                line_total = price * qty
                total += line_total
                
                # Update inventory
                self.db.update_stock(pid, -qty)
            
            # Apply tax
            final_total = total * (1 + tax_rate)
            
            logging.info(f"Order {order_id} processed gracefully. Total: ${final_total:.2f}")
            return {"status": "SUCCESS", "order_id": order_id, "total": final_total}
            
        except Exception as e:
            error_msg = f"Order {order_id} FAILED during processing. Details:\n{traceback.format_exc()}"
            logging.error(error_msg)
            
            # Report to Dynatrace
            log_error_to_dynatrace(error_msg, self.origin_id, app_name="inventory-service")
            
            return {"status": "FAILED", "order_id": order_id, "error": str(e)}

    def check_stock_levels(self, product_ids: list) -> Dict:
        """
        Check current inventory levels for multiple products.
        Returns a dictionary of product_id -> quantity.
        """
        result = {}
        for pid in product_ids:
            result[pid] = self.db.get_stock_level(pid)
        return result


class MockDatabase:
    """
    Simulates a database connection for the inventory service.
    """
    def __init__(self):
        # Mock product data
        self.products = {
            "PROD-001": {"name": "Smartphone", "price": 699.99, "stock": 120},
            "PROD-002": {"name": "Laptop", "price": 1299.99, "stock": 45},
            "PROD-003": {"name": "Tablet", "price": 349.99, "stock": 80},
            "PROD-004": {"name": "Smartwatch", "price": 199.99, "stock": 60},
            "PROD-005": {"name": "Headphones", "price": 149.99, "stock": 100},
        }
    
    def get_product_price(self, product_id: str) -> float:
        """
        Get the current price of a product.
        """
        if product_id not in self.products:
            raise ValueError(f"Product {product_id} not found")
        return self.products[product_id]["price"]
    
    def get_stock_level(self, product_id: str) -> int:
        """
        Get the current stock level of a product.
        """
        if product_id not in self.products:
            raise ValueError(f"Product {product_id} not found")
        return self.products[product_id]["stock"]
    
    def update_stock(self, product_id: str, quantity_change: int):
        """
        Update the stock level of a product.
        Positive quantity_change adds stock, negative reduces it.
        """
        if product_id not in self.products:
            raise ValueError(f"Product {product_id} not found")
        
        current = self.products[product_id]["stock"]
        new_level = current + quantity_change
        
        if new_level < 0:
            raise ValueError(f"Insufficient stock for {product_id}")
        
        self.products[product_id]["stock"] = new_level


# For testing/simulation
import traceback

if __name__ == "__main__":
    print("\n" + "="*60)
    print("\ud83d\udfe2 STARTING E-COMMERCE SYNTHETIC TRAFFIC SIMULATOR")
    print("\ud83d\udd17 Dynatrace Active. Origin ID: dt0c01.INVENTORY_1777289988")
    print("="*60)
    
    # Create service with unique origin ID
    service = InventoryService(origin_id="dt0c01.INVENTORY_1777289988")
    
    logging.info("Starting Fulfillment Manager orchestrator...")
    logging.info("Initializing connection to PostgreSQL Cluster...")
    time.sleep(0.5)
    logging.info("Database connection established.")
    
    # Simulate normal order
    print("\n[Simulation] Sending Request 1 (Normal Cart)")
    order1 = service.process_order(
        "ORD-001", 
        "CA", 
        [
            {"product_id": "PROD-001", "quantity": 1},
            {"product_id": "PROD-003", "quantity": 1}
        ]
    )
    time.sleep(1)
    
    # Simulate wholesale order
    print("\n[Simulation] Sending Request 2 (Wholesale Bulk Check)")
    order2 = service.process_order(
        "ORD-002", 
        "TX", 
        [
            {"product_id": "PROD-002", "quantity": 15}
        ]
    )
    time.sleep(1)
    
    # Simulate malformed data (string quantity)
    print("\n[Simulation] Sending Request 3 (MALFORMED DATA SPIKE!)")
    try:
        order3 = service.process_order(
            "ORD-003", 
            "NY", 
            [
                {"product_id": "PROD-004", "quantity": "5"}
            ]
        )
    except Exception as e:
        print("\n[Fulfillment System] FATAL RUNTIME ERROR ENCOUNTERED!")
        print("[Fulfillment System] Handoff to Autonomous SRE Agent...")
