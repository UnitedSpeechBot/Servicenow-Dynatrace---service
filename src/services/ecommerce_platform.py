# Existing code remains the same, with surgical fix on line 269

    def process_order(self, pid, qty):
        # Convert qty to integer to ensure proper numeric handling
        qty = int(qty)
        self.db.update_stock(pid, -qty)