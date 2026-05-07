# Existing file content with fix on line 269

# Assuming the line causing the error is:
self.db.update_stock(pid, -qty)  # Convert qty to int before negation
self.db.update_stock(pid, int(qty) * -1)