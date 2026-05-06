import logging
from typing import Dict, Optional
from src.integrations.database.manager import DatabaseManager

class EcommercePlatform:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.logger = logging.getLogger(__name__)

    def process_order(self, pid: str, qty: str):
        # Convert qty to integer to fix the TypeError
        try:
            qty = int(qty)
            self.db.update_stock(pid, -qty)  # Now qty is a valid integer
        except ValueError:
            self.logger.error(f"Invalid quantity: {qty}. Must be a numeric string.")
            raise

    # Other methods remain the same
