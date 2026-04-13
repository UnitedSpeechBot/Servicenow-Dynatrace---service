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
                err = f"WARNING: Connection pool at capacity (size={self.pool_size}), waiting for available connection"
                logging.warning(err)
                
                # Add to waiting queue instead of failing immediately
                if len(self.waiting_queue) < 10:  # Limit queue size to prevent memory issues
                    self.waiting_queue.append(True)
                    # Wait for a connection to be released
                    return self.wait_for_connection()
                else:
                    err = f"CRITICAL: Connection pool exhausted (size={self.pool_size}) and waiting queue full"
                    log_error_to_dynatrace(err, self.origin_id)
                    raise Exception("DB_POOL_EXHAUSTED")
            except Exception as e:
                log_error_to_dynatrace(f"Connection error: {str(e)}", self.origin_id)
                raise
        
        self.active_connections += 1
        return "Conn"
    
    def wait_for_connection(self):
        # In a real implementation, this would use proper synchronization
        # For this example, we'll simulate releasing a connection
        if self.active_connections > 0:
            self.active_connections -= 1
        
        # Remove from waiting queue
        if self.waiting_queue:
            self.waiting_queue.pop(0)
        
        # Now get a connection
        self.active_connections += 1
        return "Conn (after wait)"
    
    def release_connection(self):
        if self.active_connections > 0:
            self.active_connections -= 1
            return True
        return False

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
            except Exception as e:
                print(f"Connection attempt {i} failed: {e}")
                # Release some connections to allow others to proceed
                if i > 15 and connections:
                    print("Releasing a connection to free up resources")
                    connections.pop()
                    db.release_connection()
    except Exception as e:
        print(f"Application Crashed: {e}")
        
        # --- AUTONOMOUS SRE TRIGGER ---
        import traceback
        from autonomous_healer import run_autonomous_repair_loop
        # This will simulate Dynatrace calling the webhook to start the SRE Agent
        run_autonomous_repair_loop(traceback.format_exc(), db.origin_id, app_key="database-service")
    finally:
        # Clean up connections
        for _ in range(len(connections)):
            db.release_connection()