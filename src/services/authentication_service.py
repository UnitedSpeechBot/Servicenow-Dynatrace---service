import time
import uuid
import random
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import threading
import os
import sys

# Ensure 'src' is findable when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Setup basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class TokenCache:
    """In-memory token cache with expiration."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._tokens = {}  # token -> (expiry, user_id, metadata)
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
    
    def store_token(self, token: str, user_id: str, metadata: Dict = None, ttl: int = None):
        """Store a token with expiration time."""
        with self._lock:
            expiry = datetime.now() + timedelta(seconds=ttl or self._ttl)
            self._tokens[token] = (expiry, user_id, metadata or {})
            self._trigger_background_eviction()
    
    def validate_token(self, token: str) -> Optional[Dict]:
        """Check if token exists and is valid."""
        with self._lock:
            if token not in self._tokens:
                return None
                
            expiry, user_id, metadata = self._tokens[token]
            if datetime.now() > expiry:
                del self._tokens[token]
                return None
                
            return {"user_id": user_id, "metadata": metadata}
    
    def invalidate_token(self, token: str) -> bool:
        """Explicitly invalidate a token."""
        with self._lock:
            if token in self._tokens:
                del self._tokens[token]
                return True
            return False
    
    def invalidate_user_tokens(self, user_id: str) -> int:
        """Invalidate all tokens for a specific user."""
        count = 0
        with self._lock:
            tokens_to_remove = []
            for token, (_, uid, _) in list(self._tokens.items()):
                if uid == user_id:
                    tokens_to_remove.append(token)
            
            for token in tokens_to_remove:
                del self._tokens[token]
                count += 1
                
        return count
    
    def _trigger_background_eviction(self):
        """Remove expired tokens and enforce size limits."""
        with self._lock:
            # Create a copy of items to avoid RuntimeError during iteration
            token_items = list(self._tokens.items())
            
            # Remove expired tokens
            now = datetime.now()
            tokens_to_remove = []
            for tk, (expiry, _, _) in token_items:
                if now > expiry:
                    tokens_to_remove.append(tk)
            
            # Remove expired tokens from the dictionary
            for tk in tokens_to_remove:
                self._tokens.pop(tk, None)
            
            # Enforce size limit if still too large
            if len(self._tokens) > self._max_size:
                # Sort by expiry (oldest first) and remove excess
                # Create a new list from current tokens to avoid modification during iteration
                sorted_tokens = sorted(
                    list(self._tokens.items()),
                    key=lambda x: x[1][0]  # Sort by expiry timestamp
                )
                
                # Keep only the newest tokens up to max_size
                excess = len(sorted_tokens) - self._max_size
                for i in range(excess):
                    tk, _ = sorted_tokens[i]
                    self._tokens.pop(tk, None)

class IdentityProvider:
    """Simulates an identity provider with authentication and token management."""
    
    def __init__(self, origin_id: str = "dt0c01.AUTH_DEFAULT"):
        self.origin_id = origin_id
        self.cache = TokenCache(max_size=500, ttl_seconds=1800)  # 30 min TTL
        
        # Simulated user database
        self._users = {
            "user@company.com": {
                "password": "UserPass1!",
                "roles": ["user", "reporter"],
                "account_id": "ACC123456"
            },
            "admin@company.com": {
                "password": "AdminPass2@",
                "roles": ["user", "admin", "reporter"],
                "account_id": "ACC789012"
            }
        }
        
        # Rate limiting
        self._attempt_counters = {}  # IP -> (count, first_attempt_time)
        self._max_attempts = 5
        self._rate_window = 300  # 5 minutes
        
    def _is_rate_limited(self, ip_address: str) -> bool:
        """Check if an IP is currently rate limited."""
        now = time.time()
        if ip_address in self._attempt_counters:
            count, first_time = self._attempt_counters[ip_address]
            
            # Reset counter if window has passed
            if now - first_time > self._rate_window:
                self._attempt_counters[ip_address] = (1, now)
                return False
                
            # Rate limit if too many attempts
            if count >= self._max_attempts:
                return True
                
            # Increment counter
            self._attempt_counters[ip_address] = (count + 1, first_time)
            return False
        else:
            # First attempt
            self._attempt_counters[ip_address] = (1, now)
            return False
    
    def authenticate(self, username: str, password: str, ip_address: str) -> Dict:
        """Authenticate a user and return a token if successful."""
        # Check rate limiting
        if self._is_rate_limited(ip_address):
            error_msg = f"Rate limit exceeded for IP {ip_address}"
            logging.warning(error_msg)
            return {"status": "ERROR", "message": error_msg}
        
        # Check credentials
        user = self._users.get(username)
        if not user or user["password"] != password:
            error_msg = f"Invalid credentials for user {username}"
            logging.warning(error_msg)
            return {"status": "ERROR", "message": error_msg}
        
        # Generate token
        token = f"auth_{uuid.uuid4().hex}"
        
        # Store in cache
        self.cache.store_token(
            token=token,
            user_id=username,
            metadata={
                "roles": user["roles"],
                "account_id": user["account_id"],
                "ip": ip_address,
                "created": time.time()
            }
        )
        
        return {
            "status": "SUCCESS",
            "token": token,
            "user": username,
            "roles": user["roles"]
        }
    
    def validate_session(self, token: str) -> Dict:
        """Validate a session token."""
        result = self.cache.validate_token(token)
        if not result:
            return {"status": "ERROR", "message": "Invalid or expired token"}
        
        return {
            "status": "SUCCESS",
            "user": result["user_id"],
            "roles": result["metadata"].get("roles", [])
        }
    
    def logout(self, token: str) -> Dict:
        """Invalidate a session token."""
        success = self.cache.invalidate_token(token)
        return {"status": "SUCCESS" if success else "ERROR"}
    
    def logout_all_sessions(self, username: str) -> Dict:
        """Invalidate all sessions for a user."""
        count = self.cache.invalidate_user_tokens(username)
        return {"status": "SUCCESS", "sessions_terminated": count}

# --- Worker Thread Simulation ---
def worker(worker_id: int):
    """Simulate authentication traffic."""
    idp = IdentityProvider(origin_id=f"dt0c01.AUTH_WORKER_{worker_id}")
    
    # Simulate some authentication attempts
    for _ in range(3):
        res = idp.authenticate("user@company.com", "UserPass1!", f"192.168.1.{worker_id}")
        if res["status"] == "SUCCESS":
            token = res["token"]
            
            # Validate token
            idp.validate_session(token)
            
            # Logout
            idp.logout(token)
        
        time.sleep(0.5)

# --- Standard App Loop ---
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔐 STARTING AUTHENTICATION SERVICE SIMULATOR")
    print("🔗 Dynatrace Active. Origin ID: dt0c01.AUTH_CLUSTER_998A2B")
    print("="*60)
    
    # Create service with unique origin ID for tracing
    import time
    dynamic_origin = f"dt0c01.AUTH_CLUSTER_{int(time.time())}"
    # Set TTL to 0 to force immediate expiration and trigger the eviction bug
    auth_service = IdentityProvider(origin_id=dynamic_origin)
    auth_service.cache._ttl = 0 
    
    # Pre-populate some tokens
    for i in range(10):
        auth_service.cache.store_token(f"old_token_{i}", "user@company.com")
    
    # Simulate multiple worker threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    print("\n[Authentication Service] All workers completed.")
