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

# --- Standard App Loop ---
if __name__ == "__main__":
    print()
    print("="*60)
    print("  🚀 Starting Enterprise Payment Service (Production Node)")
    print("="*60)
    
    import time
    dynamic_origin = f"dt0c01.PAYMENT_{int(time.time())}"
    processor = PaymentProcessor(origin_id=dynamic_origin)

    # Simulate a day of traffic
    orders = [random.uniform(10.0, 500.0) for _ in range(8)]
    
    for idx, amount in enumerate(orders):
        print(f"\n[Request {idx+1}] Processing Order...")
        result = processor.authorize_payment(amount)
        
        if result["status"] == "SUCCESS":
            print(f"✅ Order confirmed. Txn: {result['txn_id']}")
        else:
            print(f"❌ Order failed. Reason: {result['error']}")
        
        time.sleep(0.5) 

    print("\n" + "="*60)
    print("  📈 End of Simulation Health Report")
    print("="*60)
    stats = processor.get_service_stats()
    for k, v in stats.items():
        print(f"  {k.replace('_', ' ').capitalize()}: {v}")
    print("="*60)

    # --- AUTONOMOUS SRE TRIGGER ---
    if not processor.gateway_healthy:
        print("\n🚨 CRITICAL FAILURE DETECTED: Triggering SRE Agent...")
        import traceback
        from src.core.autonomous_healer import run_autonomous_repair_loop
        
        # We manually pass the error that caused the breaker to trip
        mock_traceback = f'File "payment_processor.py", line 77, in authorize_payment\nCRITICAL: Payment Gateway Timeout for Txn at {processor.gateway_url}'
        asyncio.run(run_autonomous_repair_loop(mock_traceback, processor.origin_id, app_key="payment-service"))
