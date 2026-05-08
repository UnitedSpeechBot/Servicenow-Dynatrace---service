# Assuming the original file content remains the same, with a fix on line 278

# Existing code...

def process_order(self, pid, qty):
    # Convert qty to integer to ensure proper stock update
    qty = int(qty)
    self.db.update_stock(pid, -qty)
    # Rest of the method remains unchanged
