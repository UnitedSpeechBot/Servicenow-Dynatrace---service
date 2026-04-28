import time
import uuid
import threading
import random
from typing import Dict, Optional, List

class TokenCache:
    """Token cache with automatic expiration."""
    
    def __init__(self, max_size: int = 1000, eviction_interval: int = 60):
        self._tokens = {}
        self._max_size = max_size
        self._eviction_interval = eviction_interval
        self._lock = threading.RLock()  # Use RLock for thread safety
        
    def get_token(self, user_id: str) -> Optional[Dict]:
        """Retrieve a token by user ID if it exists and is valid."""
        with self._lock:
            token_data = self._tokens.get(user_id)
            if not token_data:
                return None
                
            # Check if token has expired
            if token_data["expires_at"] < time.time():
                del self._tokens[user_id]
                return None
                
            return token_data
    
    def store_token(self, user_id: str, token: str, expires_in: int = 3600):
        """Store a new token with expiration time."""
        with self._lock:
            # Check if we need to evict tokens due to size limit
            if len(self._tokens) >= self._max_size:
                self._evict_oldest()
                
            # Store the new token
            self._tokens[user_id] = {
                "token": token,
                "created_at": time.time(),
                "expires_at": time.time() + expires_in
            }
            
            # Trigger background eviction of expired tokens
            self._trigger_background_eviction()
    
    def invalidate(self, user_id: str) -> bool:
        """Explicitly invalidate a token."""
        with self._lock:
            if user_id in self._tokens:
                del self._tokens[user_id]
                return True
            return False
    
    def _evict_oldest(self, count: int = 10):
        """Evict the oldest tokens when cache is full."""
        with self._lock:
            if not self._tokens:
                return
                
            # Sort by creation time and remove oldest
            sorted_tokens = sorted(
                self._tokens.items(),
                key=lambda x: x[1]["created_at"]
            )
            
            # Remove the oldest entries
            for i in range(min(count, len(sorted_tokens))):
                user_id = sorted_tokens[i][0]
                del self._tokens[user_id]
    
    def _trigger_background_eviction(self):
        """Remove expired tokens from cache."""
        with self._lock:
            # Create a copy of the keys to avoid modifying during iteration
            token_keys = list(self._tokens.keys())
            for tk in token_keys:
                token_data = self._tokens.get(tk)
                if token_data and token_data["expires_at"] < time.time():
                    del self._tokens[tk]


class AuthenticationService:
    """Enterprise Authentication Service with token validation."""
    
    def __init__(self):
        self.cache = TokenCache()
        self.users = {
            "user@company.com": {
                "password": "UserPass1!",
                "roles": ["user", "admin"],
                "last_login": None
            }
        }
        
    def validate_token(self, token: str) -> Dict:
        """Validate a token and return user information."""
        # In a real system, this would verify JWT signatures, etc.
        # For this demo, we'll just check if it exists in our cache
        
        # Search through cache for matching token
        for user_id, token_data in self.cache._tokens.items():
            if token_data["token"] == token:
                if token_data["expires_at"] < time.time():
                    self.cache.invalidate(user_id)
                    return {"valid": False, "error": "Token expired"}
                    
                return {
                    "valid": True,
                    "user_id": user_id,
                    "roles": self.users.get(user_id, {}).get("roles", [])
                }
                
        return {"valid": False, "error": "Invalid token"}
    
    def authenticate(self, username: str, password: str, ip_address: str = "127.0.0.1") -> Dict:
        """Authenticate a user and issue a token."""
        user = self.users.get(username)
        
        if not user:
            return {"success": False, "error": "User not found"}
            
        if user["password"] != password:
            return {"success": False, "error": "Invalid password"}
            
        # Generate a token (in real systems, this would be a JWT)
        token = f"tk_{uuid.uuid4().hex}"
        expires_in = 3600  # 1 hour
        
        # Store in cache
        self.cache.store_token(
            username,
            token,
            expires_in
        )
        
        # Update last login
        user["last_login"] = time.time()
        
        return {
            "success": True,
            "token": token,
            "expires_in": expires_in,
            "user_id": username,
            "roles": user["roles"]
        }
    
    def logout(self, user_id: str) -> bool:
        """Log out a user by invalidating their token."""
        return self.cache.invalidate(user_id)


# For testing/simulation purposes
def worker(worker_id: int, idp: AuthenticationService):
    """Simulate authentication traffic."""
    while True:
        try:
            # Simulate login
            res = idp.authenticate("user@company.com", "UserPass1!", f"192.168.1.{worker_id}")
            
            # Simulate token validation
            if res["success"]:
                token = res["token"]
                time.sleep(random.uniform(0.1, 0.5))
                idp.validate_token(token)
                
                # Sometimes logout
                if random.random() < 0.3:
                    idp.logout("user@company.com")
        except Exception as e:
            print(f"Worker {worker_id} error: {e}")
            
        time.sleep(random.uniform(0.5, 2.0))


if __name__ == "__main__":
    # Simulate multiple clients using the auth service
    idp = AuthenticationService()
    
    # Start worker threads
    workers = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i, idp), daemon=True)
        t.start()
        workers.append(t)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
