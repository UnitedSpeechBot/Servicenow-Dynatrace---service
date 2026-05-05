import logging
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
import os
import sys

# Ensure 'src' is findable when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

class Database:
    """Mock database for e-commerce platform."""
    
    def __init__(self):
        self.products = {
            "P001": {"name": "Laptop", "price": 999.99, "stock": 10},
            "P002": {"name": "Smartphone", "price": 499.99, "stock": 20},
            "P003": {"name": "Headphones", "price": 99.99, "stock": 50},
            "P004": {"name": "Tablet", "price": 299.99, "stock": 15},
            "P005": {"name": "Smartwatch", "price": 199.99, "stock": 25},
        }
        self.orders = {}
        self.users = {
            "U001": {"name": "John Doe", "email": "john@example.com"},
            "U002": {"name": "Jane Smith", "email": "jane@example.com"},
        }
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """Get product details by ID."""
        return self.products.get(product_id)
    
    def update_stock(self, product_id: str, quantity_change: int) -> bool:
        """Update product stock."""
        if product_id not in self.products:
            return False
        
        self.products[product_id]["stock"] += quantity_change
        return True
    
    def create_order(self, user_id: str, items: List[Tuple[str, int]]) -> str:
        """Create a new order."""
        order_id = f"O{uuid.uuid4().hex[:8]}"
        self.orders[order_id] = {
            "user_id": user_id,
            "items": items,
            "status": "pending",
            "created_at": datetime.now(),
        }
        return order_id
    
    def update_order_status(self, order_id: str, status: str) -> bool:
        """Update order status."""
        if order_id not in self.orders:
            return False
        
        self.orders[order_id]["status"] = status
        return True

class PaymentGateway:
    """Mock payment gateway."""
    
    def process_payment(self, amount: float) -> Tuple[bool, str]:
        """Process a payment."""
        # Simulate payment processing
        time.sleep(0.1)
        
        # 95% success rate
        if uuid.uuid4().int % 20 != 0:
            return True, f"TXN{uuid.uuid4().hex[:10]}"
        else:
            return False, "Payment declined"

class EcommercePlatform:
    """Main e-commerce platform class."""
    
    def __init__(self):
        self.db = Database()
        self.payment_gateway = PaymentGateway()
        self.logger = logging.getLogger("ecommerce_platform")
    
    def get_product_details(self, product_id: str) -> Optional[Dict]:
        """Get product details."""
        return self.db.get_product(product_id)
    
    def check_stock(self, product_id: str, quantity: int) -> bool:
        """Check if product is in stock."""
        product = self.db.get_product(product_id)
        if not product:
            return False
        
        return product["stock"] >= quantity
    
    def process_order(self, user_id: str, items: List[Tuple[str, int]]) -> Tuple[bool, str, Optional[str]]:
        """Process an order."""
        # Check stock for all items
        for pid, qty in items:
            # Convert qty to int if it's a string
            try:
                qty = int(qty)
            except (ValueError, TypeError):
                self.logger.error(f"Invalid quantity type for product {pid}: {type(qty)}")
                return False, "Invalid quantity", None
            
            if not self.check_stock(pid, qty):
                self.logger.error(f"Insufficient stock for product {pid}")
                return False, "Insufficient stock", None
        
        # Calculate total amount
        total_amount = 0.0
        for pid, qty in items:
            product = self.db.get_product(pid)
            # Ensure qty is an integer
            qty = int(qty)
            total_amount += product["price"] * qty
        
        # Process payment
        payment_success, transaction_id = self.payment_gateway.process_payment(total_amount)
        if not payment_success:
            self.logger.error(f"Payment failed for user {user_id}")
            return False, "Payment failed", None
        
        # Create order with normalized items (ensure quantities are integers)
        normalized_items = [(pid, int(qty)) for pid, qty in items]
        order_id = self.db.create_order(user_id, normalized_items)
        
        # Update stock
        for pid, qty in normalized_items:
            self.db.update_stock(pid, -qty)
        
        # Update order status
        self.db.update_order_status(order_id, "completed")
        
        return True, "Order processed successfully", order_id
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        """Get order status."""
        if order_id not in self.db.orders:
            return None
        
        return self.db.orders[order_id]["status"]

# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Create platform instance
    platform = EcommercePlatform()
    
    # Process an order - Fixed: Converting strings to ints
    try:
        success, message, order_id = platform.process_order(
            "U001", [("P001", "1"), ("P003", "2")]
        )
        if success:
            print(f"Order {order_id} created: {message}")
        else:
            print(f"Order failed: {message}")
    except Exception as e:
        import traceback
        err_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        print(f"❌ CRASHED: {err_msg}")
        # Report to mirror
        try:
            from src.services.payment_processor import log_error_to_dynatrace
            log_error_to_dynatrace(err_msg, "dt0c01.INVENTORY_1777364649", "ecommerce-platform")
        except ImportError:
            logging.error("Could not import log_error_to_dynatrace")