# Root Cause Analysis Report

## Executive Summary
Multiple critical issues were identified across several microservices in the e-commerce platform. The primary issues include:

1. **Inventory Service Type Error**: Data type mismatch causing order processing failures
2. **Notification Service Email Failures**: SMTP connection issues preventing customer notifications
3. **Authentication Service Concurrency Bug**: Dictionary modification during iteration causing authentication failures

## Detailed Analysis

### Issue 1: Inventory Service Type Error
**Severity**: Critical  
**Service**: inventory-service

#### Problem
The inventory service is failing to process orders due to a type error when attempting to update stock quantities.

#### Root Cause
The quantity parameter (`qty`) is being received as a string instead of an integer, causing the unary minus operation (`-qty`) to fail with the error: `TypeError: bad operand type for unary -: 'str'`.

#### Evidence
```python
Traceback (most recent call last):
  File "/Users/a1436985/Downloads/servicenow_dyntrace copy/src/services/ecommerce_platform.py", line 269, in process_order
    self.db.update_stock(pid, -qty)
                              ^^^^
TypeError: bad operand type for unary -: 'str'
```

#### Impact
Order processing failures, particularly for order ORD-003, preventing inventory updates and potentially causing inventory discrepancies.

---

### Issue 2: Notification Service Email Failures
**Severity**: High  
**Service**: notification-service

#### Problem
The notification service is unable to send order confirmation emails to customers.

#### Root Cause
SMTP connection to the internal mail server (smtp.internal:587) is being refused, indicating either the mail server is down or there are network connectivity issues.

#### Evidence
```
ERROR: Failed to send email to customer@example.com. Reason: SMTP connection refused at smtp.internal:587
```

#### Impact
Customers are not receiving order confirmation emails, p