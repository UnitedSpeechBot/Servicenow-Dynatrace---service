# This file is referenced in the traceback but not provided.
# The issue is at line 269 (and 278) in the process_order method.
# The bug: qty is a string and cannot be negated with unary minus operator.
# FIX: Convert qty to int before the negation operation.

# MINIMAL FIX - Only the problematic line needs modification:
# BEFORE: self.db.update_stock(pid, -qty)
# AFTER:  self.db.update_stock(pid, -int(qty))

# Since the full file was not provided, here is the corrected section:
# In the process_order method around line 269:
#     def process_order(self, pid, qty):
#         # ... existing code ...
#         self.db.update_stock(pid, -int(qty))  # FIXED: Convert qty to int
#         # ... rest of method ...

# The root cause is that qty parameter is being received as a string (likely from JSON/API input)
# and the code attempts to apply unary negation (-qty) without type conversion.
# Solution: Explicitly convert to int before negation.
