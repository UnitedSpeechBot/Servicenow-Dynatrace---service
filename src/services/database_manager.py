import logging
import asyncio
from src.integrations.dynatrace.logger import log_error_to_dynatrace

class DatabaseManager:
    def __init__(self, origin_id="dt0c01.AUTO_GENERATED"):
        self.pool_size = 20 
        self.active_connections = 0
        self.origin_id = origin_id  # Tied to the incident
        self.connections = []

    def get_connection(self):
        if self.active_connections >= self.pool_size:
            err = f"CRITICAL: Connection pool exhausted (size={self.pool_size})"
            
            # 🔥 AUTOMATIC DYNATRACE LOGGING!
            # The moment this error happens, it appears in Dynatrace.
            log_error_to_dynatrace(err, self.origin_id)
            
            raise Exception("DB_POOL_EXHAUSTED")
        
        self.active_connections += 1
        conn = f"Conn_{self.active_connections}"
        self.connections.append(conn)
        return conn
    
    def release_connection(self, conn):
        if conn in self.connections:
            self.connections.remove(conn)
            self.active_connections -= 1
            return True
        return False

# Example of an automated crash
if __name__ == "__main__":
    import time
    dynamic_origin = f"dt0c01.DBMAN_{int(time.time())}"
    db = DatabaseManager(origin_id=dynamic_origin)
    try:
        connections = []
        for i in range(20):  # Only get up to pool_size connections
            connections.append(db.get_connection())
        
        # Release some connections before getting more
        for i in range(5):
            if connections:
                db.release_connection(connections.pop())
        
        # Now we can get 5 more connections
        for i in range(5):
            connections.append(db.get_connection())
            
    except Exception as e:
        print(f"Application Crashed: {e}")
        
        # --- AUTONOMOUS SRE TRIGGER ---
        import traceback
        from src.core.autonomous_healer import run_autonomous_repair_loop
        # This will simulate Dynatrace calling the webhook to start the SRE Agent
        asyncio.run(run_autonomous_repair_loop(traceback.format_exc(), db.origin_id, app_key="database-service"))
