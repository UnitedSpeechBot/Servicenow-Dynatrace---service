```python
import logging
import asyncio
from dynatrace_logger import log_error_to_dynatrace

class DatabaseManager:
    def __init__(self, origin_id="dt0c01.AUTO_GENERATED"):
        self.pool_size = 20 
        self.active_connections = 0
        self.origin_id = origin_id  # Tied to the incident

    def get_connection(self):
        if self.active_connections >= self.pool_size:
            err = f"CRITICAL: Connection pool exhausted (size={self.pool_size})"
            
            # 🔥 AUTOMATIC DYNATRACE LOGGING!
            # The moment this error happens, it appears in Dynatrace.
            log_error_to_dynatrace(err, self.origin_id)
            
            raise Exception("DB_POOL_EXHAUSTED")
        
        self.active_connections += 1
        return "Conn"

# Example of an automated crash
if __name__ == "__main__":
    # In a real app, 'origin_id' would come from the transaction headers
    db = DatabaseManager(origin_id="dt0c01.UNL3GU5ZFLQMVWL3Y4M3X2DG")
    try:
        for i in range(25): 
            try:
                db.get_connection()
            except Exception as e:
                print(f"Connection error: {e}")
                break
    except Exception as e:
        print(f"Application Crashed: {e}")
        
        # --- AUTONOMOUS SRE TRIGGER ---
        import traceback
        from autonomous_healer import run_autonomous_repair_loop
        # This will simulate Dynatrace calling the webhook to start the SRE Agent
        asyncio.run(run_autonomous_repair_loop(traceback.format_exc(), db.origin_id, app_key="database-service"))
```