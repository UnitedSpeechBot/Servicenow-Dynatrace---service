# Existing file content with surgical fix

def process_order(self, pid, qty):
    # Convert qty to integer to resolve type error
    qty = int(qty)
    self.db.update_stock(pid, -qty)
