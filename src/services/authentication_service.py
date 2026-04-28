import time
import uuid
import random
import threading
from typing import Dict, List, Optional, Tuple

class TokenCache:
    """Token cache with automatic expiration."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._tokens = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
    
    def get_token(self, user_id: str) -> Optional[Dict]:
        """Retrieve a token by user ID if it exists and is valid."""
        with self._lock:
            token_data = self._tokens.get(user_id)
            if not token_data:
                return None
                
            token, timestamp = token_data
            if time.time() - timestamp > self._ttl_seconds:
                # Token expired
                del self._tokens[user_id]
                return None
                
            return token
    
    def store_token(self, user_id: str, token: Dict) -> None:
        """Store a token with the current timestamp."""
        with self._lock:
            self._tokens[user_id] = (token, time.time())
            self._trigger_background_eviction()
    
    def invalidate(self, user_id: str) -> bool:
        """Invalidate a specific token."""
        with self._lock:
            if user_id in self._tokens:
                del self._tokens[user_id]
                return True
            return False
    
    def _trigger_background_eviction(self) -> None:
        """Trigger background eviction if cache is too large."""
        with self._lock:
            if len(self._tokens) <= self._max_size:
                return
                
            # Create a copy of the keys to avoid modifying during iteration
            tokens_to_check = list(self._tokens.keys())
            
            # Find expired tokens
            now = time.time()
            expired = []
            for tk in tokens_to_check:
                _, timestamp = self._tokens.get(tk, (None, 0))
                if now - timestamp > self._ttl_seconds:
                    expired.append(tk)
            
            # Remove expired tokens
            for tk in expired:
                if tk in self._tokens:  # Check again in case it was removed
                    del self._tokens[tk]
            
            # If still too many tokens, remove oldest
            if len(self._tokens) > self._max_size:
                # Sort by timestamp (oldest first)
                sorted_tokens = sorted(
                    self._tokens.items(),
                    key=lambda x: x[1][1]  # Sort by timestamp
                )
                
                # Remove oldest tokens until we're under the limit
                tokens_to_remove = len(sorted_tokens) - self._max_size
                for i in range(tokens_to_remove):
                    if i < len(sorted_tokens):
                        user_id = sorted_tokens[i][0]
                        if user_id in self._tokens:  # Check again
                            del self._tokens[user_id]


class AuthenticationService:
    """Authentication service with token management."""
    
    def __init__(self, cache_size: int = 1000, token_ttl: int = 3600):
        self.cache = TokenCache(max_size=cache_size, ttl_seconds=token_ttl)
        self.failed_attempts = {}
        self.lockout_threshold = 5
        self.lockout_duration = 300  # 5 minutes
        
    def authenticate(self, username: str, password: str, ip_address: str) -> Dict:
        """Authenticate a user and return a token."""
        # Check if IP is locked out
        if self._is_ip_locked(ip_address):
            return {
                "status": "error",
                "message": "Too many failed attempts. Try again later."
            }
        
        # Check if user exists in cache
        existing = self.cache.get_token(username)
        if existing:
            return {
                "status": "success",
                "token": existing["token"],
                "expires": existing["expires"],
                "cached": True
            }
        
        # Simulate authentication logic
        if self._validate_credentials(username, password):
            # Reset failed attempts on success
            if ip_address in self.failed_attempts:
                del self.failed_attempts[ip_address]
            
            # Generate new token
            token = str(uuid.uuid4())
            expires = int(time.time()) + 3600
            
            token_data = {
                "token": token,
                "user": username,
                "expires": expires
            }
            
            # Store in cache
            self.cache.store_token(
                username,
                token_data
            )
            
            return {
                "status": "success",
                "token": token,
                "expires": expires,
                "cached": False
            }
        else:
            # Track failed attempt
            self._record_failed_attempt(ip_address)
            
            return {
                "status": "error",
                "message": "Invalid credentials"
            }
    
    def validate_token(self, token: str) -> Dict:
        """Validate a token."""
        # Simulate token validation
        # In a real system, we would look up the token in a database
        if not token or len(token) < 10:
            return {"valid": False, "reason": "Invalid token format"}
        
        # For demo purposes, we'll say 10% of tokens are invalid
        if random.random() < 0.1:
            return {"valid": False, "reason": "Token expired or revoked"}
        
        return {"valid": True, "user": f"user_{token[-8:]}"}
    
    def _validate_credentials(self, username: str, password: str) -> bool:
        """Validate user credentials."""
        # Simplified validation for demo
        if not username or not password:
            return False
        
        # Demo: accept any password ending with '!'
        if password.endswith('!'):
            return True
        
        return False
    
    def _is_ip_locked(self, ip_address: str) -> bool:
        """Check if an IP is locked out due to too many failed attempts."""
        if ip_address not in self.failed_attempts:
            return False
        
        attempts, timestamp = self.failed_attempts[ip_address]
        
        # Check if lockout period has expired
        if time.time() - timestamp > self.lockout_duration:
            del self.failed_attempts[ip_address]
            return False
        
        # Check if attempts exceed threshold
        return attempts >= self.lockout_threshold
    
    def _record_failed_attempt(self, ip_address: str) -> None:
        """Record a failed authentication attempt."""
        if ip_address not in self.failed_attempts:
            self.failed_attempts[ip_address] = (1, time.time())
        else:
            attempts, _ = self.failed_attempts[ip_address]
            self.failed_attempts[ip_address] = (attempts + 1, time.time())


# Demo worker threads to simulate load
def worker(worker_id: int, iterations: int = 100):
    """Simulate authentication worker."""
    idp = AuthenticationService()
    
    for i in range(iterations):
        # Simulate random user activity
        action = random.choice(["auth", "validate"])
        
        if action == "auth":
            res = idp.authenticate("user@company.com", "UserPass1!", f"192.168.1.{worker_id}")
        else:
            token = str(uuid.uuid4())
            res = idp.validate_token(token)
        
        # Simulate some processing time
        time.sleep(0.01)


# Main demo
if __name__ == "__main__":
    print("Starting Authentication Service demo...")
    
    # Start some worker threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    print("Demo completed.")
