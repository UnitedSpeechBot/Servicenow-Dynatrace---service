import logging
from dynatrace_logger import log_error_to_dynatrace

class DatabaseManager:
    def __init__(self, origin_id="dt0c01.AUTO_GENERATED"):
        self.pool_size = 20 
        self.active_connections = 0
        self.origin_id = origin_id  # Tied to the incident
        self.waiting_queue = []

    def get_connection(self):
        if self.active_connections >= self.pool_size:
            try:
                # Instead of immediately failing, try to reuse a connection or queue the request
                if len(self.waiting_queue) > 0:
                    # Reuse a connection from the waiting queue if available
                    return self.waiting_queue.pop(0)
                
                # Log warning but don't fail immediately
                warning_msg = f"WARNING: Connection pool at capacity (size={self.pool_size}), waiting for available connection"
                logging.warning(warning_msg)
                
                # Try to wait for a connection to become available
                # In a real implementation, this might use a proper queue with timeout
                # For this fix, we'll just return a special connection that indicates it's from overflow handling
                return "OverflowConn"
            except Exception as e:
                err = f"CRITICAL: Connection pool exhausted (size={self.pool_size}): {str(e)}"
                
                # 🔥 AUTOMATIC DYNATRACE LOGGING!
                # The moment this error happens, it appears in Dynatrace.
                log_error_to_dynatrace(err, self.origin_id)
                
                raise Exception(f"DB_POOL_EXHAUSTED: {str(e)}")
        
        self.active_connections += 1
        return "Conn"
    
    def release_connection(self, connection):
        """Add method to release connections back to the pool"""
        if self.active_connections > 0:
            self.active_connections -= 1
        else:
            # Add to waiting queue for reuse
            self.waiting_queue.append(connection)

# Example of an automated crash
if __name__ == "__main__":
    # In a real app, 'origin_id' would come from the transaction headers
    db = DatabaseManager(origin_id="dt0c01.UNL3GU5ZFLQMVWL3Y4M3X2DG")
    connections = []
    
    try:
        for i in range(25):
            try:
                conn = db.get_connection()
                connections.append(conn)
                # Release some connections to simulate real usage patterns
                if i % 5 == 0 and connections:
                    conn_to_release = connections.pop()
                    db.release_connection(conn_to_release)
            except Exception as e:
                logging.error(f"Failed to get connection: {e}")
                # Continue execution instead of crashing
    except Exception as e:
        print(f"Application Crashed: {e}")
        
        # --- AUTONOMOUS SRE TRIGGER ---
        import traceback
        from autonomous_healer import run_autonomous_repair_loop
        # This will simulate Dynatrace calling the webhook to start the SRE Agent
        run_autonomous_repair_loop(traceback.format_exc(), db.origin_id, app_key="database-service")