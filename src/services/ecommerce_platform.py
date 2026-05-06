import logging

class EcommercePlatform:
    def __init__(self, db_connection):
        self.db = db_connection
        self.logger = logging.getLogger(__name__)

    def process_order(self, pid, qty):
        # Convert qty to integer to ensure proper stock update
        qty = int(qty)
        self.db.update_stock(pid, -qty)

    # Rest of the class remains unchanged
