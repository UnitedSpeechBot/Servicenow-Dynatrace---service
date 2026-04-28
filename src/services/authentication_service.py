import time
import asyncio
import uuid
import random
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta

# Setup basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class TokenCache:
    """Token cache with expiration and background eviction."""
    
    def __init__(self, max_size: int = 1000, eviction_interval: int = 60):
        self._tokens = {}
        self._max_size = max_size
        self._eviction_interval = eviction_interval
        self._last_eviction = time.time()
        
    def get_token(self, user_id: str) -> Optional[Dict]:
        """Retrieve a token if it exists and is valid."""
        if user_id not in self._tokens:
            return None
            
        token_data = self._tokens[user_id]
        if token_data["expires_at"] < time.time():
            # Token expired, remove it
            del self._tokens[user_id]
            return None
            
        return token_data
        
    def store_token(self, user_id: str, token: str, expires_in: int = 3600):
        """Store a token with expiration time."""
        self._tokens[user_id] = {
            "token": token,
            "created_at": time.time(),
            "expires_at": time.time() + expires_in
        }
        
        # Check if we need to run eviction
        if len(self._tokens) > self._max_size or \
           (time.time() - self._last_eviction) > self._eviction_interval:
            self._trigger_background_eviction()
            
    def _trigger_background_eviction(self):
        """Remove expired tokens to prevent memory leaks."""
        self._last_eviction = time.time()
        now = time.time()
        
        # FIX: Create a copy of keys to avoid dictionary changed size during iteration
        for tk in list(self._tokens.keys()):
            if self._tokens[tk]["expires_at"] < now:
                del self._tokens[tk]
                
    def get_stats(self) -> Dict:
        """Return cache statistics."""
        return {
            "size": len(self._tokens),
            "max_size": self._max_size,
            "last_eviction": self._last_eviction
        }

class AuthenticationService:
    """Authentication service with token validation and caching."""
    
    def __init__(self, origin_id: str = "dt0c01.AUTH_CLUSTER_DEFAULT"):
        self.origin_id = origin_id
        self.cache = TokenCache()
        self.users_db = {
            "user@company.com": {
                "password": "UserPass1!",
                "roles": ["user", "admin"],
                "last_login": None
            }
        }
        
    def validate_token(self, token: str) -> Dict:
        """Validate a token and return user information."""
        # In a real system, this would verify JWT signatures, etc.
        try:
            # Simple simulation - tokens are UUIDs with user ID appended
            if not token or len(token) < 40:
                return {"valid": False, "error": "Invalid token format"}
                
            parts = token.split("_")
            if len(parts) != 2:
                return {"valid": False, "error": "Malformed token"}
                
            user_id = parts[1]
            
            # Check cache first
            cached = self.cache.get_token(user_id)
            if cached and cached["token"] == token:
                return {"valid": True, "user_id": user_id}
                
            # In a real system, we'd verify with the database
            # This is just a simulation
            if user_id in self.users_db:
                return {"valid": True, "user_id": user_id}
                
            return {"valid": False, "error": "Unknown user"}
            
        except Exception as e:
            logging.error(f"Token validation error: {str(e)}")
            return {"valid": False, "error": str(e)}
            
    def authenticate(self, username: str, password: str, ip_address: str = "127.0.0.1") -> Dict:
        """Authenticate a user and issue a token."""
        try:
            if username not in self.users_db:
                return {"success": False, "error": "Invalid credentials"}
                
            user = self.users_db[username]
            if user["password"] != password:
                return {"success": False, "error": "Invalid credentials"}
                
            # Generate a token (in real systems, this would be a JWT)
            token = f"{uuid.uuid4()}__{username}"
            
            # Store in cache
            self.cache.store_token(
                username,
                token,
                expires_in=3600  # 1 hour
            )
            
            # Update last login
            self.users_db[username]["last_login"] = datetime.now().isoformat()
            
            return {
                "success": True,
                "token": token,
                "expires_in": 3600,
                "user": {
                    "username": username,
                    "roles": user["roles"]
                }
            }
            
        except Exception as e:
            logging.error(f"Authentication error for {username}: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def logout(self, token: str) -> bool:
        """Invalidate a token."""
        validation = self.validate_token(token)
        if not validation["valid"]:
            return False
            
        # In a real system, we'd add this token to a blocklist
        # or remove it from the active tokens store
        return True
        
    def get_service_stats(self) -> Dict:
        """Return service statistics."""
        return {
            "service": "authentication-service",
            "cache_stats": self.cache.get_stats(),
            "user_count": len(self.users_db)
        }

# Simulate multiple workers for load testing
async def worker(worker_id: int, total_requests: int = 10):
    """Simulate authentication worker."""
    idp = AuthenticationService(origin_id=f"dt0c01.AUTH_CLUSTER_{worker_id:04d}")
    
    for i in range(total_requests):
        try:
            # Simulate authentication requests
            res = idp.authenticate("user@company.com", "UserPass1!", f"192.168.1.{worker_id}")
            if res["success"]:
                token = res["token"]
                # Validate the token we just created
                val_res = idp.validate_token(token)
                if not val_res["valid"]:
                    logging.error(f"Worker {worker_id}: Token validation failed!")
            else:
                logging.error(f"Worker {worker_id}: Authentication failed: {res['error']}")
                
            # Random delay between requests
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
        except Exception as e:
            logging.error(f"Worker {worker_id} error: {str(e)}")
            
    logging.info(f"Worker {worker_id} completed {total_requests} requests")

async def run_load_test(num_workers: int = 5, requests_per_worker: int = 20):
    """Run a load test with multiple workers."""
    tasks = []
    for i in range(num_workers):
        tasks.append(worker(i, requests_per_worker))
        
    await asyncio.gather(*tasks)
    logging.info(f"Load test complete: {num_workers} workers, {requests_per_worker} requests each")

# --- Standard App Loop ---
if __name__ == "__main__":
    print()
    print("="*60)
    print("  🔐 Starting Authentication Service (Production Node)")
    print("="*60)
    
    # Run a load test
    asyncio.run(run_load_test(5, 20))
    
    print("\n" + "="*60)
    print("  📈 End of Simulation Health Report")
    print("="*60)
    
    idp = AuthenticationService()
    stats = idp.get_service_stats()
    for k, v in stats.items():
        print(f"  {k.replace('_', ' ').capitalize()}: {v}")
    print("="*60)
