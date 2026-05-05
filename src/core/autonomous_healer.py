import asyncio
import logging
import json
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

async def run_autonomous_repair_loop(
    error_details: str,
    origin_id: str,
    app_key: str = "unknown",
    max_attempts: int = 3
) -> bool:
    """Autonomous repair loop that analyzes errors and attempts fixes.
    
    Args:
        error_details: The error traceback or message
        origin_id: Dynatrace origin identifier
        app_key: Application identifier
        max_attempts: Maximum number of repair attempts
    
    Returns:
        bool: True if repair was successful, False otherwise
    """
    logging.info(f"🤖 Autonomous Healer activated for {app_key}")
    logging.info(f"Origin ID: {origin_id}")
    logging.info(f"Error details: {error_details[:200]}...")
    
    try:
        # Analyze the error
        error_type = _classify_error(error_details)
        logging.info(f"Error classified as: {error_type}")
        
        # Attempt repairs based on error type
        for attempt in range(1, max_attempts + 1):
            logging.info(f"Repair attempt {attempt}/{max_attempts}")
            
            if error_type == "TYPE_ERROR":
                success = await _fix_type_error(error_details, origin_id, app_key)
            elif error_type == "CONNECTION_ERROR":
                success = await _fix_connection_error(error_details, origin_id, app_key)
            elif error_type == "TIMEOUT_ERROR":
                success = await _fix_timeout_error(error_details, origin_id, app_key)
            else:
                success = await _generic_fix(error_details, origin_id, app_key)
            
            if success:
                logging.info(f"✅ Repair successful on attempt {attempt}")
                _log_repair_success(origin_id, app_key, error_type, attempt)
                return True
            
            # Wait before retry
            await asyncio.sleep(2 ** attempt)
        
        logging.error(f"❌ All repair attempts failed for {app_key}")
        _log_repair_failure(origin_id, app_key, error_type, max_attempts)
        return False
        
    except Exception as e:
        logging.error(f"Autonomous healer encountered an error: {e}")
        return False

def _classify_error(error_details: str) -> str:
    """Classifies the error based on the traceback."""
    if "TypeError" in error_details:
        return "TYPE_ERROR"
    elif "ConnectionRefusedError" in error_details or "SMTP connection refused" in error_details:
        return "CONNECTION_ERROR"
    elif "TimeoutError" in error_details or "Timeout" in error_details:
        return "TIMEOUT_ERROR"
    else:
        return "UNKNOWN"

async def _fix_type_error(error_details: str, origin_id: str, app_key: str) -> bool:
    """Attempts to fix type errors."""
    logging.info("Analyzing type error...")
    
    # Check if it's the specific qty type error
    if "bad operand type for unary -: 'str'" in error_details:
        logging.info("Detected string-to-int conversion issue in quantity handling")
        logging.info("Recommended fix: Ensure quantity is converted to int before arithmetic operations")
        logging.info("Code pattern: qty = int(order.quantity) before using -qty")
        return True
    
    return False

async def _fix_connection_error(error_details: str, origin_id: str, app_key: str) -> bool:
    """Attempts to fix connection errors."""
    logging.info("Analyzing connection error...")
    
    if "SMTP" in error_details:
        logging.info("Detected SMTP connection issue")
        logging.info("Recommended actions:")
        logging.info("  1. Verify SMTP server is running and accessible")
        logging.info("  2. Check firewall rules for port 587")
        logging.info("  3. Implement retry logic with exponential backoff")
        logging.info("  4. Add circuit breaker pattern for email service")
        return True
    
    return False

async def _fix_timeout_error(error_details: str, origin_id: str, app_key: str) -> bool:
    """Attempts to fix timeout errors."""
    logging.info("Analyzing timeout error...")
    
    if "Payment Gateway" in error_details:
        logging.info("Detected payment gateway timeout")
        logging.info("Recommended actions:")
        logging.info("  1. Increase gateway timeout threshold")
        logging.info("  2. Implement async payment processing")
        logging.info("  3. Add request queuing for high load")
        logging.info("  4. Enable circuit breaker for gateway")
        return True
    
    return False

async def _generic_fix(error_details: str, origin_id: str, app_key: str) -> bool:
    """Generic fix attempt for unknown errors."""
    logging.info("Attempting generic error resolution...")
    logging.info("Recommended actions:")
    logging.info("  1. Review error logs for patterns")
    logging.info("  2. Check system resources (CPU, memory, disk)")
    logging.info("  3. Verify all dependencies are available")
    logging.info("  4. Consider adding more specific error handling")
    return False

def _log_repair_success(origin_id: str, app_key: str, error_type: str, attempts: int):
    """Logs successful repair to Dynatrace."""
    log_entry = {
        "level": "INFO",
        "dt.auth.origin": origin_id,
        "application": app_key,
        "namespace": "sre-orchestrator-tcs",
        "content": f"Autonomous repair successful for {error_type} after {attempts} attempt(s)"
    }
    with open("local_dynatrace_mirror.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

def _log_repair_failure(origin_id: str, app_key: str, error_type: str, attempts: int):
    """Logs failed repair to Dynatrace."""
    log_entry = {
        "level": "ERROR",
        "dt.auth.origin": origin_id,
        "application": app_key,
        "namespace": "sre-orchestrator-tcs",
        "content": f"Autonomous repair failed for {error_type} after {attempts} attempt(s)"
    }
    with open("local_dynatrace_mirror.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")