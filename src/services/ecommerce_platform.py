import time
import asyncio
import uuid
import random
import logging
from typing import Dict, List, Optional
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def log_error_to_dynatrace(error_msg: str, origin_id: str, app_name: str = "unknown"):
    """Appends a real error log to the local mirror for the SRE Agent to find."""
    log_entry = {
        "level": "ERROR",
        "dt.auth.origin": origin_id,
        "application": app_name,
        "namespace": "sre-orchestrator-tcs",
        "content": error_msg
    }
    with open("local_dynatrace_mirror.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
    logging.info(f"  [Dynatrace] 📡 Log reported to mirror — origin: {origin_id}")

class DatabaseManager:
    """Simulates a database connection for inventory management."""
    
    def __init__(self):
        self.inventory = {
            "prod_001": {"name": "Laptop", "stock": 50, "price": 999.99},
            "prod_002": {"name": "Mouse", "stock": 200, "price": 29.99},
            "prod_003": {"name": "Keyboard", "stock": 150, "price": 79.99}
        }
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        return self.inventory.get(product_id)
    
    def update_stock(self, product_id: str, quantity_delta: int) -> bool:
        """Updates stock by the given delta (positive to add, negative to subtract)."""
        if product_id not in self.inventory:
            return False
        
        new_stock = self.inventory[product_id]["stock"] + quantity_delta
        if new_stock < 0:
            return False
        
        self.inventory[product_id]["stock"] = new_stock
        return True
    
    def get_stock(self, product_id: str) -> int:
        product = self.inventory.get(product_id)
        return product["stock"] if product else 0

class EmailService:
    """Handles email notifications."""
    
    def __init__(self, origin_id: str):
        self.origin_id = origin_id
        self.smtp_host = "smtp.internal"
        self.smtp_port = 587
    
    def send_email(self, recipient: str, subject: str, body: str) -> bool:
        """Simulates sending an email."""
        try:
            logging.info(f"Sending email to {recipient}: {subject}")
            # Simulate email sending with 20% failure rate
            if random.random() < 0.2:
                raise ConnectionRefusedError(f"SMTP connection refused at {self.smtp_host}:{self.smtp_port}")
            time.sleep(0.1)
            return True
        except Exception as e:
            err_msg = f"ERROR: Failed to send email to {recipient}. Reason: {e}"
            logging.error(err_msg)
            log_error_to_dynatrace(err_msg, self.origin_id, app_name="email-service")
            return False

class PaymentProcessor:
    """Handles payment processing."""
    
    def __init__(self, origin_id: str):
        self.origin_id = origin_id
        self.gateway_url = "https://api.stripe-mock.internal/v1"
        self.gateway_timeout = 10.0
    
    def authorize_payment(self, amount: float, currency: str = "USD") -> Dict:
        """Authorizes a payment transaction."""
        txn_id = str(uuid.uuid4())
        logging.info(f"Authorizing payment: {currency}{amount} (Txn: {txn_id})")
        
        try:
            # Simulate payment processing with 10% failure rate
            processing_time = random.uniform(0.1, 0.5)
            time.sleep(processing_time)
            
            if random.random() < 0.1:
                raise TimeoutError(f"Payment Gateway Timeout for Txn {txn_id} at {self.gateway_url}")
            
            return {"status": "SUCCESS", "txn_id": txn_id}
        except Exception as e:
            err_msg = f"CRITICAL: {e}"
            logging.error(err_msg)
            log_error_to_dynatrace(err_msg, self.origin_id, app_name="payment-service")
            return {"status": "FAILED", "txn_id": txn_id, "error": str(e)}

class OrderRequest:
    """Represents an order request."""
    
    def __init__(self, product_id: str, quantity: int, customer_email: str):
        self.product_id = product_id
        self.quantity = quantity
        self.customer_email = customer_email
        self.order_id = str(uuid.uuid4())

class EcommerceOrderManager:
    """Main order processing manager."""
    
    def __init__(self, origin_id: str = "dt0c01.ECOMMERCE"):
        self.origin_id = origin_id
        self.db = DatabaseManager()
        self.email_service = EmailService(origin_id)
        self.payment_processor = PaymentProcessor(origin_id)
    
    def process_order(self, order: OrderRequest) -> Dict:
        """Processes a complete order workflow."""
        logging.info(f"Processing order {order.order_id} for product {order.product_id}")
        
        try:
            # Step 1: Validate product and stock
            product = self.db.get_product(order.product_id)
            if not product:
                raise ValueError(f"Product {order.product_id} not found")
            
            # FIX: Convert quantity to int to ensure proper type
            qty = int(order.quantity)
            
            current_stock = self.db.get_stock(order.product_id)
            if current_stock < qty:
                raise ValueError(f"Insufficient stock for {order.product_id}. Available: {current_stock}, Requested: {qty}")
            
            # Step 2: Calculate total and process payment
            total_amount = product["price"] * qty
            payment_result = self.payment_processor.authorize_payment(total_amount)
            
            if payment_result["status"] != "SUCCESS":
                raise Exception(f"Payment failed: {payment_result.get('error', 'Unknown error')}")
            
            # Step 3: Update inventory (FIX: pass negative integer, not string)
            if not self.db.update_stock(order.product_id, -qty):
                raise Exception(f"Failed to update stock for {order.product_id}")
            
            # Step 4: Send confirmation email
            self.email_service.send_email(
                order.customer_email,
                "Order Confirmation",
                f"Your order {order.order_id} has been confirmed. Total: ${total_amount:.2f}"
            )
            
            logging.info(f"Order {order.order_id} completed successfully")
            return {
                "status": "SUCCESS",
                "order_id": order.order_id,
                "txn_id": payment_result["txn_id"],
                "total": total_amount
            }
            
        except Exception as e:
            import traceback
            err_msg = f"Traceback (most recent call last):\n{traceback.format_exc()}"
            logging.error(f"Order processing failed: {e}")
            log_error_to_dynatrace(err_msg, self.origin_id, app_name="ecommerce-platform")
            
            # Trigger autonomous healing for critical errors
            if "TypeError" in str(type(e).__name__) or "Payment" in str(e):
                try:
                    from src.core.autonomous_healer import run_autonomous_repair_loop
                    error_details = f"File \"/Users/a1436985/Downloads/servicenow_dyntrace/src/services/ecommerce_platform.py\", line 269, in process_order\n{err_msg}"
                    # Don't block on healing - just log it
                    logging.warning("Critical error detected - autonomous healing would be triggered in production")
                except ImportError:
                    logging.warning("Autonomous healer module not available")
            
            return {
                "status": "FAILED",
                "order_id": order.order_id,
                "error": str(e)
            }

def run_simulation():
    """Runs a simulation of the ecommerce platform."""
    print("\n" + "="*60)
    print("  🛒 Starting E-Commerce Platform Simulation")
    print("="*60 + "\n")
    
    manager = EcommerceOrderManager()
    
    # Create test orders with proper integer quantities
    test_orders = [
        OrderRequest("prod_001", 2, "customer@example.com"),
        OrderRequest("prod_002", 5, "customer@example.com"),
        OrderRequest("prod_003", 1, "customer@example.com"),
        OrderRequest("prod_001", 3, "customer@example.com"),
        OrderRequest("prod_002", 10, "customer@example.com"),
    ]
    
    results = []
    for order in test_orders:
        result = manager.process_order(order)
        results.append(result)
        time.sleep(0.5)
    
    # Print summary
    print("\n" + "="*60)
    print("  📊 Simulation Summary")
    print("="*60)
    successful = sum(1 for r in results if r["status"] == "SUCCESS")
    failed = len(results) - successful
    print(f"  Total Orders: {len(results)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_simulation()