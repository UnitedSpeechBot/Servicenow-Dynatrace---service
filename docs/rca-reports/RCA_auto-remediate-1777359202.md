# Root Cause Analysis Report

## Incident Summary
**Date:** April 28, 2026  
**Time:** 06:51:21 UTC  
**Affected Services:** 
- Inventory Service
- Authentication Service
- Payment Processor
- SRE Orchestrator

## Issue Description
Multiple critical errors were observed across several microservices, with two primary failure patterns:

1. **Inventory Service Type Error**: Failed to process orders due to type mismatch when updating stock quantities
2. **Authentication Service Runtime Error**: Token cache management failures causing authentication issues

## Root Causes

### Issue 1: Inventory Service Type Error
**Root Cause:** The inventory service is attempting to apply a unary negative operator (`-`) to a string value instead of a numeric value when updating stock quantities.

**Evidence:**
```
TypeError: bad operand type for unary -: 'str'
```

The error occurs in `ecommerce_platform.py` at line 269 in the `process_order` method when calling `self.db.update_stock(pid, -qty)`. The `qty` variable is being passed as a string instead of an integer, causing the operation to fail.

### Issue 2: Authentication Service Dictionary Iteration Error
**Root Cause:** Concurrent modification of a dictionary during iteration in the token cache eviction process.

**Evidence:**
```
RuntimeError: dictionary changed size during iteration
```

The error occurs in `authentication_service.py` at line 112 in the `_trigger_background_eviction` method when iterating through `self._tokens.keys()`. The dictionary is being modified during iteration, which is not thread-safe in Python.

### Secondary Issue: SMTP Connection Failure
**Evidence:**
```
ERROR: Failed to send email to customer@example.com. Reason: SMTP connection refused at smtp.internal:587
```

The payment processor is unable to send confirmation emails due to SMTP connection issues.

## Impact
1. **Order Processing Failures**: Order ORD-003 and potentially others failed to process correctly
2. **Authentication Failures**: Users li