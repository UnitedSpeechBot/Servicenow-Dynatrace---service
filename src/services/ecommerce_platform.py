# Existing code remains the same

def process_order(self, pid, qty):
    # Convert qty to integer to ensure proper stock update
    qty = int(qty)
    self.db.update_stock(pid, -qty)