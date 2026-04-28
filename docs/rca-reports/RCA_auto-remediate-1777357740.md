# Root Cause Analysis Report

## Incident Summary
**Date:** April 28, 2026  
**Time:** 06:26:53 UTC  
**Affected Services:** 
- Authentication Service
- Inventory Service
- Payment Service

## Issue Description
Multiple critical errors were observed across several microservices, with the most severe impact on the Authentication Service, causing authentication failures due to a concurrent modification exception.

## Root Cause
The primary issue was identified in the Authentication Service where a thread-safety violation occurred in the token cache management. Specifically, the `_trigger_background_eviction()` method attempted to iterate through a dictionary while it was being modified concurrently, resulting in a `RuntimeError: dictionary changed size during iteration` exception.

## Detailed Analysis

### Authentication Service Issue
The most critical issue was in the Authentication Service where multiple instances of the following error occurred:

```
RuntimeError: dictionary changed size during iteration
```

This error occurred in the `_trigger_background_eviction()` method (line 112) when attempting to iterate through `self._tokens.keys()` while the dictionary was being modified concurrently by another thread or process. This is a classic thread-safety violation in Python.

The error propagated through the following call stack:
1. `worker()` function calls `authenticate()`
2. `authenticate()` calls `cache.store_token()`
3. `store_token()` calls `_trigger_background_eviction()`
4. `_trigger_background_eviction()` attempts to iterate through `self._tokens.keys()`

### Inventory Service Issue
A secondary issue was detected in the Inventory Service where a type error occurred:

```
TypeError: bad operand type for unary -: 'str'
```

This error occurred in the `process_order` method (line 269) when attempting to update stock with `self.db.update_stock(pid, -qty)`. The error indicates that `qty` is a string instead of a numeric type, causing the unary minus operation 