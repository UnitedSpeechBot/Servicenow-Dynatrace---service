import time
import asyncio
import uuid
import random
import logging
from typing import Dict, Optional
from src.integrations.dynatrace.logger import log_error_to_dynatrace

# Setup basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class TokenCache:
    """Token cache with automatic expiration."""
    
    def __init__(self):
        self._tokens = {}
        self._expiry = {}
        self.default_ttl = 3600  # 1 hour
        
    def get_token(self, token_id: str) -> Optional[Dict]:
        """Retrieve a token if it exists and is not expired."""
        if token_id not in self._tokens:
            return None
            
        if time.time() > self._expiry.get(token_id, 0):
            # Token expired
            del self._tokens[token_id]
            del self._expiry[token_id]
            return None
            
        return self._tokens[token_id]
        
    def store_token(self, token_id: str, token_data: Dict, ttl: int = None):
        """Store a token with expiration."""
        if ttl is None:
            ttl = self.default_ttl
            
        self._tokens[token_id] = token_data
        self._expiry[token_id] = time.time() + ttl
        
        # Trigger background cleanup of expired tokens
        self._trigger_background_eviction()
        
    def invalidate(self, token_id: str):
        """Explicitly invalidate a token."""
        if token_id in self._tokens:
            del self._tokens[token_id]
        if token_id in self._expiry:
            del self._expiry[token_id]
            
    def _trigger_background_eviction(self):
        """Remove expired tokens."""
        now = time.time()
        tokens_to_remove = []
        
        for tk in list(self._tokens.keys()):
            if now > self._expiry.get(tk, 0):
                tokens_to_remove.append(tk)
                
        for tk in tokens_to_remove:
            if tk in self._tokens:
                del self._tokens[tk]
            if tk in self._expiry:
                del self._expiry[tk]


class AuthenticationService:
    """Enterprise Authentication Service with token validation."""
    
    def __init__(self, origin_id: str = "dt0c01.AUTH_CLUSTER_998A2B"):
        self.origin_id = origin_id
        self.cache = TokenCache()
        self.failed_attempts = {}
        self.lockout_threshold = 5
        self.lockout_duration = 300  # 5 minutes
        
    def validate_token(self, token: str) -> Dict:
        """Validate a token and return its associated data."""
        if not token:
            return {"valid": False, "error": "No token provided"}
            
        # Check cache first
        cached = self.cache.get_token(token)
        if cached:
            return {"valid": True, "user": cached.get("user"), "scopes": cached.get("scopes")}
            
        # Token not in cache or expired
        return {"valid": False, "error": "Invalid or expired token"}
        
    def _is_account_locked(self, username: str) -> bool:
        """Check if an account is temporarily locked due to failed attempts."""
        if username not in self.failed_attempts:
            return False
            
        attempts, lockout_time = self.failed_attempts[username]
        
        if attempts >= self.lockout_threshold:
            # Account is locked, check if lockout period has expired
            if time.time() < lockout_time + self.lockout_duration:
                return True
            else:
                # Lockout period expired, reset counter
                del self.failed_attempts[username]
                
        return False
        
    def _record_failed_attempt(self, username: str):
        """Record a failed authentication attempt."""
        if username not in self.failed_attempts:
            self.failed_attempts[username] = [1, time.time()]
        else:
            attempts, _ = self.failed_attempts[username]
            self.failed_attempts[username] = [attempts + 1, time.time()]
            
    def authenticate(self, username: str, password: str, ip_address: str = "127.0.0.1") -> Dict:
        """Authenticate a user and issue a token."""
        # Check for account lockout
        if self._is_account_locked(username):
            err_msg = f"Account temporarily locked: {username}"
            log_error_to_dynatrace(err_msg, self.origin_id, "authentication-service")
            return {"authenticated": False, "error": "Account locked due to too many failed attempts"}
            
        # In a real system, we would validate against a database
        # This is a simplified example
        if username == "user@company.com" and password == "UserPass1!":
            # Successful authentication
            token_id = str(uuid.uuid4())
            user_data = {
                "user": username,
                "scopes": ["read", "write"],
                "ip": ip_address,
                "issued_at": time.time()
            }
            
            # Store in cache
            self.cache.store_token(
                token_id,
                user_data,
                ttl=3600  # 1 hour
            )
            
            return {
                "authenticated": True,
                "token": token_id,
                "expires_in": 3600,
                "user": username
            }
        else:
            # Failed authentication
            self._record_failed_attempt(username)
            err_msg = f"Failed authentication attempt for user: {username} from IP: {ip_address}"
            log_error_to_dynatrace(err_msg, self.origin_id, "authentication-service")
            
            return {"authenticated": False, "error": "Invalid credentials"}
    
    def revoke_token(self, token: str) -> bool:
        """Explicitly revoke/invalidate a token."""
        self.cache.invalidate(token)
        return True
        
    def get_service_stats(self) -> Dict:
        """Return service statistics."""
        return {
            "service": "authentication-service",
            "status": "healthy",
            "locked_accounts": len([u for u, (a, _) in self.failed_attempts.items() if a >= self.lockout_threshold])
        }


# --- Worker Simulation ---
async def worker(worker_id: int, idp: AuthenticationService):
    """Simulate authentication worker process."""
    while True:
        try:
            # Simulate authentication requests
            res = idp.authenticate("user@company.com", "UserPass1!", f"192.168.1.{worker_id}")
            if res["authenticated"]:
                # Simulate token validation
                token = res["token"]
                idp.validate_token(token)
                
                # Sometimes revoke tokens
                if random.random() < 0.3:
                    idp.revoke_token(token)
        except Exception as e:
            err_msg = f"CRITICAL ERROR in auth worker {worker_id}: {str(e)}"
            log_error_to_dynatrace(err_msg, idp.origin_id, "authentication-service")
            
        await asyncio.sleep(random.uniform(0.5, 2.0))


async def run_simulation():
    """Run a simulation of the authentication service with multiple workers."""
    print("\n" + "="*60)
    print("  🔐 Starting Enterprise Authentication Service")
    print("="*60)
    
    # Create service instance
    auth_service = AuthenticationService()
    
    # Start worker tasks
    workers = []
    for i in range(3):
        workers.append(asyncio.create_task(worker(i+1, auth_service)))
        
    try:
        # Run for a while
        await asyncio.sleep(30)
    finally:
        # Clean up
        for w in workers:
            w.cancel()
            
    print("\n" + "="*60)
    print("  📊 Authentication Service Statistics")
    print("="*60)
    
    stats = auth_service.get_service_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")


# --- Main Entry Point ---
if __name__ == "__main__":
    asyncio.run(run_simulation())
