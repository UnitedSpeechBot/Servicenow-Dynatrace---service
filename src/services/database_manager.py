import logging
import asyncio
from src.integrations.dynatrace.logger import log_error_to_dynatrace

class DatabaseManager:
    def __init__(self, origin_id="dt0c01.AUTO_GENERATED"):
        self.pool_size = 20 
        self.active_connections = 0
        self.origin_id = origin_id  # Tied to the incident
        self.connection_queue = []
        self.max_queue_size = 50

    def get_connection(self):
        if self.active_connections >= self.pool_size:
            # Instead of raising an exception, queue the connection request
            if len(self.connection_queue) < self.max_queue_size:
                logging.warning(f"Connection pool full. Request queued (queue size: {len(self.connection_queue) + 1})")
                self.connection_queue.append(time.time())
                # Wait for a connection to become available
                while self.active_connections >= self.pool_size:
                    time.sleep(0.1)
                # Connection is now available
                self.connection_queue.pop(0)
            else:
                err = f"CRITICAL: Connection pool exhausted (size={self.pool_size}) and queue full (size={self.max_queue_size})"
                
                # 🔥 AUTOMATIC DYNATRACE LOGGING!
                # The moment this error happens, it appears in Dynatrace.
                log_error_to_dynatrace(err, self.origin_id)
                
                raise Exception("DB_POOL_AND_QUEUE_EXHAUSTED")
        
        self.active_connections += 1
        return "Conn"
    
    def release_connection(self, conn):
        """Release a connection back to the pool"""
        if self.active_connections > 0:
            self.active_connections -= 1
            logging.debug(f"Connection released. Active connections: {self.active_connections}")
        return True

# Example of an automated crash
if __name__ == "__main__":
    import time
    dynamic_origin = f"dt0c01.DBMAN_{int(time.time())}"
    db = DatabaseManager(origin_id=dynamic_origin)
    try:
        connections = []
        for i in range(25): 
            connections.append(db.get_connection())
        # Release some connections to demonstrate the queue processing
        for i in range(5):
            db.release_connection(connections.pop())
    except Exception as e:
        print(f"Application Crashed: {e}")
        
        # --- AUTONOMOUS SRE TRIGGER ---
        import traceback
        from src.core.autonomous_healer import run_autonomous_repair_loop
        # This will simulate Dynatrace calling the webhook to start the SRE Agent
        asyncio.run(run_autonomous_repair_loop(traceback.format_exc(), db.origin_id, app_key="database-service"))
