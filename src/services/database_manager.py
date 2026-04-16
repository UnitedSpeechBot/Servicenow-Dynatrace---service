import logging
import asyncio
from src.integrations.dynatrace.logger import log_error_to_dynatrace

class DatabaseManager:
    def __init__(self, origin_id="dt0c01.AUTO_GENERATED"):
        self.pool_size = 20 
        self.active_connections = 0
        self.origin_id = origin_id  # Tied to the incident
        self.connection_queue = []  # Queue for waiting connections
        self.max_queue_size = 30    # Maximum queue size

    def get_connection(self):
        if self.active_connections >= self.pool_size:
            # Fixed: Implement connection pooling with queue instead of failing immediately
            if len(self.connection_queue) < self.max_queue_size:
                logging.warning(f"Connection pool full (size={self.pool_size}). Adding to wait queue.")
                # In a real implementation, we would wait for a connection to become available
                # For this simulation, we'll just log the queuing
                self.connection_queue.append(time.time())
                # Wait for a connection to become available (simulated)
                time.sleep(0.1)
                self.connection_queue.pop(0)  # Remove from queue
                return "QueuedConn"
            else:
                err = f"CRITICAL: Connection pool exhausted (size={self.pool_size}) and queue full"
                # 🔥 AUTOMATIC DYNATRACE LOGGING!
                log_error_to_dynatrace(err, self.origin_id)
                raise Exception("DB_POOL_EXHAUSTED")
        
        self.active_connections += 1
        return "Conn"
    
    def release_connection(self, conn):
        """Release a connection back to the pool"""
        if self.active_connections > 0:
            self.active_connections -= 1
            return True
        return False

# Example of an automated crash
if __name__ == "__main__":
    import time
    dynamic_origin = f"dt0c01.DBMAN_{int(time.time())}"
    db = DatabaseManager(origin_id=dynamic_origin)
    try:
        for i in range(25): db.get_connection()
    except Exception as e:
        print(f"Application Crashed: {e}")
        
        # --- AUTONOMOUS SRE TRIGGER ---
        import traceback
        from src.core.autonomous_healer import run_autonomous_repair_loop
        # This will simulate Dynatrace calling the webhook to start the SRE Agent
        asyncio.run(run_autonomous_repair_loop(traceback.format_exc(), db.origin_id, app_key="database-service"))
