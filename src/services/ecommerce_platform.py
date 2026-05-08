# This file contains the ecommerce platform service logic
# Original implementation with minimal surgical fix applied

class EcommercePlatform:
    def __init__(self, db):
        self.db = db
    
    def process_order(self, pid, qty):
        """
        Process an order by updating stock inventory.
        
        Args:
            pid: Product ID
            qty: Quantity to reduce from stock (should be numeric)
        """
        # Convert qty to integer to ensure numeric type for unary negation
        qty = int(qty)
        self.db.update_stock(pid, -qty)
