import logging
import random
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

class Database:
    """Mock database for inventory management."""
    
    def __init__(self):
        self.stock = {
            "PROD001": 120,
            "PROD002": 85,
            "PROD003": 32,
            "PROD004": 64,
        }
        self.prices = {
            "PROD001": 129.99,
            "PROD002": 89.99,
            "PROD003": 299.99,
            "PROD004": 59.99,
        }
        self.names = {
            "PROD001": "Premium Headphones",
            "PROD002": "Wireless Mouse",
            "PROD003": "4K Monitor",
            "PROD004": "Keyboard",
        }
        
    def get_stock(self, product_id: str) -> int:
        """Get current stock level for a product."""
        return self.stock.get(product_id, 0)
    
    def update_stock(self, product_id: str, quantity_change: int) -> bool:
        """Update stock levels."""
        if product_id not in self.stock:
            return False
        
        new_level = self.stock[product_id] + quantity_change
        if new_level < 0:
            return False
        
        self.stock[product_id] = new_level
        return True
    
    def get_price(self, product_id: str) -> float:
        """Get price for a product."""
        return self.prices.get(product_id, 0.0)
    
    def get_name(self, product_id: str) -> str:
        """Get name for a product."""
        return self.names.get(product_id, "Unknown Product")


class InventoryService:
    """Main inventory management service."""
    
    def __init__(self):
        self.logger = logging.getLogger("InventoryService")
        self.db = Database()
        self.tax_rates = {
            "CA": 0.0725,  # California
            "NY": 0.045,   # New York
            "TX": 0.0625,  # Texas
            "FL": 0.06,    # Florida
            "IL": 0.0625,  # Illinois
            "DEFAULT": 0.05,  # Default rate
        }
        
    def check_stock(self, product_id: str) -> int:
        """Check current stock level for a product."""
        return self.db.get_stock(product_id)
    
    def calculate_tax(self, subtotal: float, state: str) -> float:
        """Calculate tax based on state."""
        rate = self.tax_rates.get(state, self.tax_rates["DEFAULT"])
        return subtotal * rate
    
    def calculate_total(self, items: List[Tuple[str, int]], state: str) -> Dict:
        """Calculate order total with tax."""
        subtotal = 0.0
        item_details = []
        
        for pid, qty in items:
            price = self.db.get_price(pid)
            item_total = price * qty
            subtotal += item_total
            
            item_details.append({
                "product_id": pid,
                "name": self.db.get_name(pid),
                "quantity": qty,
                "unit_price": price,
                "total": item_total
            })
        
        tax = self.calculate_tax(subtotal, state)
        total = subtotal + tax
        
        return {
            "items": item_details,
            "subtotal": subtotal,
            "tax_rate": self.tax_rates.get(state, self.tax_rates["DEFAULT"]),
            "tax": tax,
            "total": total
        }
    
    def process_order(self, order_id: str, state: str, items: List[Tuple[str, Union[int, str]]]) -> Dict:
        """Process a complete order."""
        self.logger.info(f"Processing Order {order_id} for State {state} with {len(items)} items.")
        
        # Check stock availability
        for pid, qty in items:
            current_stock = self.check_stock(pid)
            if current_stock < qty:
                self.logger.error(f"Insufficient stock for {pid}. Requested: {qty}, Available: {current_stock}")
                return {"status": "error", "message": f"Insufficient stock for {pid}"}
        
        # Calculate totals
        try:
            order_details = self.calculate_total(items, state)
        except Exception as e:
            self.logger.error(f"Error calculating total: {str(e)}")
            return {"status": "error", "message": f"Calculation error: {str(e)}"}
        
        # Update inventory
        try:
            for pid, qty in items:
                # Convert qty to int if it's a string
                if isinstance(qty, str):
                    qty = int(qty)
                self.db.update_stock(pid, -qty)
        except Exception as e:
            self.logger.error(f"Error updating inventory: {str(e)}")
            return {"status": "error", "message": f"Inventory update error: {str(e)}"}
        
        # Apply wholesale discount for large orders
        if sum(qty for _, qty in items) > 10:
            self.logger.info("Applying bulk wholesale discount.")
            discount = order_details["subtotal"] * 0.15
            order_details["discount"] = discount
            order_details["total"] -= discount
        
        self.logger.info(f"Order {order_id} processed gracefully. Total: ${order_details['total']:.2f}")
        return {"status": "success", "order_id": order_id, **order_details}


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S,%f",
)

# Example usage
if __name__ == "__main__":
    service = InventoryService()
    
    # Process a sample order
    order = service.process_order(
        "ORD-12345",
        "CA",
        [("PROD001", 2), ("PROD003", 1)]
    )
    
    print(f"Order processed: {order}")
