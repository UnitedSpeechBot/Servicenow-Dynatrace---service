import time
import asyncio
import uuid
import random
import logging
from typing import Dict, Optional
from src.integrations.dynatrace.logger import log_error_to_dynatrace

# Setup basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class PaymentProcessor:
    """
    A Production-grade Payment Processing Service.
    Handles transaction orchestration, external gateway calls, and automated logging.
    """

    def __init__(self, origin_id: str = "dt0c01.AUTO_GENERATED"):
        self.origin_id = origin_id
        self.gateway_url = "https://api.stripe-mock.internal/v1"
        self.max_retries = 3
        # Simulation of Circuit Breaker State
        self.gateway_healthy = True
        self.failure_count = 0
        self.threshold = 5

    def _call_external_gateway(self, payload: Dict) -> bool:
        """Simulates an API call to a third-party payment provider like Stripe."""
        # ⚠️ THE BUG: If the payload is too large, it times out.
        # This simulates a production instability issue.
        if len(str(payload)) > 500:
            time.sleep(2)  # Latency Spike
            return False
            
        # Simulate random gateway failures (10% chance)
        if random.random() < 0.10:
            return False
        
        return True

    def _send_email_notification(self, user_email: str, status: str):
        """Simulates sending an order confirmation email."""
        # This matches the SMTP error from your Dynatrace logs!
        smtp_host = "smtp.example.com:587"
        try:
            logging.info(f"Sending {status} email to {user_email} via {smtp_host}...")
            # Simulation of connection refusal
            if "internal" in smtp_host:
                raise ConnectionRefusedError(f"SMTP connection refused at {smtp_host}")
        except Exception as e:
            err_msg = f"ERROR: Failed to send email to {user_email}. Reason: {e}"
            logging.error(err_msg)
            # Automatic reporting to Dynatrace
            log_error_to_dynatrace(err_msg, self.origin_id, app_name="notification-service")

    def authorize_payment(self, amount: float, currency: str = "USD") -> Dict:
        """Main entry point for payment authorization."""
        txn_id = str(uuid.uuid4())
        logging.info(f"Starting Auth for Txn: {txn_id} | Amount: {currency}{amount}")

        payload = {
            "transaction_id": txn_id,
            "amount": amount,
            "currency": currency,
            "timestamp": time.time()
        }

        # Step 1: Check Database (using our manager)
        # In a real app, you would import DatabaseManager here.
        # But we simulate the result for this file's standalone logic.
        logging.info("Checking database connection availability...")

        # Step 2: Call Gateway
        success = self._call_external_gateway(payload)
        
        if not success:
            self.failure_count += 1
            err_msg = f"CRITICAL: Payment Gateway Timeout for Txn {txn_id} at {self.gateway_url}"
            logging.error(err_msg)
            
            # 🔥 AUTOMATIC DYNATRACE REPORTING
            log_error_to_dynatrace(err_msg, self.origin_id, app_name="payment-service")
            
            if self.failure_count >= self.threshold:
                self.gateway_healthy = False
                logging.warning("CIRCUIT BREAKER OPENED: Gateway is unresponsive.")

            return {"status": "FAILED", "txn_id": txn_id, "error": "Gateway Timeout"}

        # Step 3: Send Confirmation
        self._send_email_notification("customer@example.com", "SUCCESS")

        logging.info(f"Payment Successful: {txn_id}")
        return {"status": "SUCCESS", "txn_id": txn_id}

    def refund_transaction(self, txn_id: str) -> bool:
        """Simulates a refund operation."""
        logging.info(f"Initiating refund for Txn: {txn_id}")
        # Standard logic
        time.sleep(0.5)
        return True

    def get_service_stats(self) -> Dict:
        """Returns health metrics for Prometheus/Dynatrace."""
        return {
            "service": "payment-processor",
            "gateway_status": "UP" if self.gateway_healthy else "DOWN",
            "failure_rate": f"{self.failure_count / (self.threshold * 2) * 100}%",
            "uptime": "99.99%"
        }

class DatabaseManager:
    """Simulates a database connection manager with inventory operations."""
    
    def __init__(self):
        self.connected = True
        self.inventory = {
            "PROD-001": {"name": "Premium Widget", "price": 129.99, "stock": 42},
            "PROD-002": {"name": "Budget Widget", "price": 59.99, "stock": 253},
            "PROD-003": {"name": "Enterprise Solution", "price": 1999.99, "stock": 5},
        }
        
    def get_product(self, product_id: str) -> dict:
        """Get product details by ID"""
        return self.inventory.get(product_id, {})
        
    def update_stock(self, product_id: str, quantity_change: int):
        """Update inventory stock levels"""
        if product_id in self.inventory:
            self.inventory[product_id]["stock"] += quantity_change
            return True
        return False

class EcommerceService:
    """Main e-commerce platform service handling orders and inventory."""
    
    def __init__(self, origin_id: str = "dt0c01.INVENTORY_AUTO"):
        self.origin_id = origin_id
        self.db = DatabaseManager()
        self.payment = PaymentProcessor(origin_id)
        self.tax_rates = {
            "CA": 0.0725,  # California
            "NY": 0.045,   # New York
            "TX": 0.0625,  # Texas
            "FL": 0.06,    # Florida
        }
        
    def calculate_tax(self, subtotal: float, state: str) -> float:
        """Calculate tax based on state"""
        rate = self.tax_rates.get(state, 0.05)  # Default 5% for other states
        return subtotal * rate
        
    def process_order(self, order_id: str, items: list, state: str):
        """Process a complete order with multiple items"""
        logging.info(f"Processing Order {order_id} for State {state} with {len(items)} items.")
        
        subtotal = 0.0
        for item in items:
            pid = item.get("product_id")
            qty = item.get("quantity")
            
            # Get product details
            product = self.db.get_product(pid)
            if not product:
                err_msg = f"Product {pid} not found in inventory"
                logging.error(err_msg)
                log_error_to_dynatrace(err_msg, self.origin_id, "inventory-service")
                continue
                
            # Check if we have enough stock
            if product["stock"] < qty:
                err_msg = f"Insufficient stock for {pid}: requested {qty}, have {product['stock']}"
                logging.error(err_msg)
                log_error_to_dynatrace(err_msg, self.origin_id, "inventory-service")
                continue
                
            # Update inventory
            try:
                # Convert qty to int if it's a string
                if isinstance(qty, str):
                    qty = int(qty)
                self.db.update_stock(pid, -qty)
                item_total = product["price"] * qty
                subtotal += item_total
            except Exception as e:
                err_msg = f"Error processing item {pid}: {str(e)}"
                logging.error(err_msg)
                log_error_to_dynatrace(err_msg, self.origin_id, "inventory-service")
                
        # Apply wholesale discount for large orders
        if subtotal > 1000:
            logging.info("Applying bulk wholesale discount.")
            subtotal *= 0.9  # 10% discount
            
        # Calculate tax
        tax = self.calculate_tax(subtotal, state)
        total = subtotal + tax
        
        # Process payment
        payment_result = self.payment.authorize_payment(total)
        
        if payment_result["status"] == "SUCCESS":
            logging.info(f"Order {order_id} processed gracefully. Total: ${total:.2f}")
            return {"status": "SUCCESS", "order_id": order_id, "total": total}
        else:
            err_msg = f"Order {order_id} FAILED during processing. Details:\n{payment_result['error']}"
            logging.error(err_msg)
            log_error_to_dynatrace(err_msg, self.origin_id, "inventory-service")
            return {"status": "FAILED", "order_id": order_id, "error": payment_result["error"]}

# --- Standard App Loop ---
if __name__ == "__main__":
    print("\n" + "="*60)
    print("\ud83d\udfe2 STARTING E-COMMERCE SYNTHETIC TRAFFIC SIMULATOR")
    print("\ud83d\udd17 Dynatrace Active. Origin ID: dt0c01.INVENTORY_1777289988")
    print("="*60)
    
    # Create service with unique origin ID for tracing
    import time
    dynamic_origin = f"dt0c01.INVENTORY_{int(time.time())}"
    service = EcommerceService(origin_id=dynamic_origin)
    
    # Simulate a few orders
    print("\n[Simulation] Sending Request 1 (Normal Cart)")
    order1 = service.process_order("ORD-001", [
        {"product_id": "PROD-001", "quantity": 2},
        {"product_id": "PROD-002", "quantity": 1}
    ], "CA")
    
    time.sleep(1)
    
    print("\n[Simulation] Sending Request 2 (Wholesale Bulk Check)")
    order2 = service.process_order("ORD-002", [
        {"product_id": "PROD-003", "quantity": 1}
    ], "TX")
    
    time.sleep(1)
    
    print("\n[Simulation] Sending Request 3 (MALFORMED DATA SPIKE!)")
    # This order has a string quantity which will cause the error
    order3 = service.process_order("ORD-003", [
        {"product_id": "PROD-001", "quantity": "5"}
    ], "NY")
    
    if order3["status"] == "FAILED":
        print("\n[Fulfillment System] FATAL RUNTIME ERROR ENCOUNTERED!")
        print("[Fulfillment System] Handoff to Autonomous SRE Agent...")
        
        # Trigger autonomous healing
        from src.core.autonomous_healer import run_autonomous_repair_loop
        import traceback
        
        # We manually pass the error that caused the issue
        mock_traceback = traceback.format_exc()
        asyncio.run(run_autonomous_repair_loop(mock_traceback, service.origin_id, app_key="inventory-service"))
