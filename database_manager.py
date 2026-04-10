import logging
import time

# Simulation of a Production Database Connection Pool
class DatabaseManager:
    def __init__(self):
        # ⚠️ THE BUG: This pool size is too small for high-traffic events!
        # Our AI Agent will suggest increasing this to 50.
        self.pool_size = 20 
        self.timeout_ms = 1000 
        self.active_connections = 0
        logging.info(f"Database initialized with pool_size={self.pool_size}")

    def get_connection(self):
        """Simulates acquiring a connection from the pool."""
        if self.active_connections >= self.pool_size:
            logging.error(f"Connection timeout: failed to acquire connection from pool after {self.timeout_ms}ms")
            raise Exception("DB_POOL_EXHAUSTED")
        
        self.active_connections += 1
        return "Connection_Object"

    def release_connection(self):
        if self.active_connections > 0:
            self.active_connections -= 1

# Example Usage
if __name__ == "__main__":
    db = DatabaseManager()
    try:
        # Simulate heavy load
        for i in range(25):
            print(f"Request {i}: Acquiring connection...")
            db.get_connection()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
