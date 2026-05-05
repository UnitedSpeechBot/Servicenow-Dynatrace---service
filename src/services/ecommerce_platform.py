import time
import random
import logging
import asyncio
from typing import Dict, List, Optional
from src.services.payment_processor import PaymentProcessor
from src.integrations.dynatrace.logger import log_error_to_dynatrace

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class DatabaseManager:
    """Mock database for inventory and order management."""
    
    def __init__(self):
        self.inventory = {
            "P001": {"name": "Laptop", "stock": 50, "price": 999.99},
            "P002": {"name": "Mouse", "stock": 200, "price": 29.99},
            "P003": {"name": "Keyboard", "stock": 150, "price": 79.99},
        }
        self.orders = []
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """Retrieve product information."""
        return self.inventory.get(product_id)
    
    def update_stock(self, product_id: str, quantity_delta: int) -> bool:
        """Update stock levels. Positive delta adds stock, negative removes."""
        if product_id not in self.inventory:
            return False
        
        new_stock = self.inventory[product_id]["stock"] + quantity_delta
        if new_stock < 0:
            logging.error(f"Insufficient stock for {product_id}")
            return False
        
        self.inventory[product_id]["stock"] = new_stock
        return True
    
    def create_order(self, order_data: Dict) -> str:
        """Create a new order record."""
        order_id = f"ORD-{len(self.orders) + 1:05d}"
        order_data["order_id"] = order_id
        order_data["timestamp"] = time.time()
        self.orders.append(order_data)
        return order_id

class EcommercePlatform:
    """Main e-commerce platform orchestrator."""
    
    def __init__(self, origin_id: str = "dt0c01.ECOMMERCE"):
        self.origin_id = origin_id
        self.db = DatabaseManager()
        self.payment_processor = PaymentProcessor(origin_id=origin_id)
        self.order_count = 0
    
    def process_order(self, order_request: Dict) -> Dict:
        """
        Process a complete order workflow:
        1. Validate inventory
        2. Reserve stock
        3. Process payment
        4. Confirm order
        """
        self.order_count += 1
        logging.info(f"\n{'='*60}")
        logging.info(f"Processing Order #{self.order_count}")
        logging.info(f"{'='*60}")
        
        try:
            # Extract order details
            product_id = order_request.get("product_id")
            quantity = order_request.get("quantity")
            customer_email = order_request.get("customer_email", "customer@example.com")
            
            # FIX: Ensure quantity is converted to integer
            if isinstance(quantity, str):
                try:
                    quantity = int(quantity)
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid quantity value: {quantity}. Must be a number.")
            
            if not product_id or quantity is None:
                raise ValueError("Missing required fields: product_id or quantity")
            
            # Step 1: Check inventory
            product = self.db.get_product(product_id)
            if not product:
                return {
                    "status": "FAILED",
                    "error": f"Product {product_id} not found"
                }
            
            if product["stock"] < quantity:
                return {
                    "status": "FAILED",
                    "error": f"Insufficient stock. Available: {product['stock']}, Requested: {quantity}"
                }
            
            # Step 2: Calculate total and process payment
            total_amount = product["price"] * quantity
            logging.info(f"Order Details: {quantity}x {product['name']} = ${total_amount:.2f}")
            
            payment_result = self.payment_processor.authorize_payment(total_amount)
            
            if payment_result["status"] != "SUCCESS":
                return {
                    "status": "FAILED",
                    "error": "Payment authorization failed",
                    "payment_details": payment_result
                }
            
            # Step 3: Update inventory (FIX: quantity is now guaranteed to be int)
            stock_updated = self.db.update_stock(product_id, -quantity)
            if not stock_updated:
                # Rollback payment if stock update fails
                logging.error("Stock update failed, initiating payment refund")
                self.payment_processor.refund_transaction(payment_result["txn_id"])
                return {
                    "status": "FAILED",
                    "error": "Stock update failed"
                }
            
            # Step 4: Create order record
            order_data = {
                "product_id": product_id,
                "product_name": product["name"],
                "quantity": quantity,
                "total_amount": total_amount,
                "customer_email": customer_email,
                "payment_txn_id": payment_result["txn_id"]
            }
            order_id = self.db.create_order(order_data)
            
            logging.info(f"✅ Order {order_id} completed successfully")
            return {
                "status": "SUCCESS",
                "order_id": order_id,
                "transaction_id": payment_result["txn_id"],
                "total_amount": total_amount
            }
            
        except Exception as e:
            error_msg = f"Order processing failed: {str(e)}"
            logging.error(error_msg)
            import traceback
            tb_str = traceback.format_exc()
            logging.error(tb_str)
            
            # Log to Dynatrace
            log_error_to_dynatrace(tb_str, self.origin_id, app_name="ecommerce-platform")
            
            # Trigger autonomous healing
            try:
                from src.core.autonomous_healer import run_autonomous_repair_loop
                import src.config as config
                asyncio.run(run_autonomous_repair_loop(tb_str, config.dt_origin_id, app_key=config.app_key))
            except Exception as heal_error:
                logging.error(f"Autonomous healing failed: {heal_error}")
            
            return {
                "status": "FAILED",
                "error": error_msg
            }
    
    def get_inventory_status(self) -> Dict:
        """Return current inventory levels."""
        return {
            "inventory": self.db.inventory,
            "total_orders": len(self.db.orders),
            "orders_processed": self.order_count
        }

def run_simulation():
    """Run a simulation of the e-commerce platform."""
    print("\n" + "="*60)
    print("  🛒 E-Commerce Platform Simulation")
    print("="*60 + "\n")
    
    platform = EcommercePlatform()
    
    # Test orders with various scenarios
    test_orders = [
        {"product_id": "P001", "quantity": 2, "customer_email": "customer1@example.com"},
        {"product_id": "P002", "quantity": "5", "customer_email": "customer2@example.com"},  # String quantity (will be fixed)
        {"product_id": "P003", "quantity": 1, "customer_email": "customer3@example.com"},
        {"product_id": "P001", "quantity": "3", "customer_email": "customer4@example.com"},  # String quantity (will be fixed)
        {"product_id": "P999", "quantity": 1, "customer_email": "customer5@example.com"},  # Non-existent product
    ]
    
    results = []
    for order in test_orders:
        result = platform.process_order(order)
        results.append(result)
        time.sleep(0.5)
    
    # Print summary
    print("\n" + "="*60)
    print("  📊 Simulation Summary")
    print("="*60)
    
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    failed_count = len(results) - success_count
    
    print(f"Total Orders: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    
    inventory_status = platform.get_inventory_status()
    print("\nFinal Inventory:")
    for pid, details in inventory_status["inventory"].items():
        print(f"  {pid}: {details['name']} - Stock: {details['stock']}")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    run_simulation()