import time
import uuid
import random
import threading
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from src.integrations.dynatrace.logger import log_error_to_dynatrace

# Setup basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class TokenCache:
    """
    In-memory token cache with TTL expiration.
    Handles token storage, retrieval, and background eviction.
    """
    def __init__(self, default_ttl_seconds: int = 3600):
        self._tokens = {}  # token_id -> {token_data, expiry}
        self._default_ttl = default_ttl_seconds
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        
        # Start background cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._background_cleanup,
            daemon=True
        )
        self._cleanup_thread.start()
    
    def get_token(self, token_id: str) -> Optional[Dict]:
        """Retrieve a token if it exists and is not expired."""
        with self._lock:
            token_data = self._tokens.get(token_id)
            if not token_data:
                return None
                
            # Check if token has expired
            if token_data["expiry"] < datetime.now():
                del self._tokens[token_id]
                return None
                
            return token_data["data"]
    
    def store_token(self, token_id: str, token_data: Dict, ttl_seconds: Optional[int] = None):
        """Store a token with expiration time."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expiry = datetime.now() + timedelta(seconds=ttl)
        
        with self._lock:
            self._tokens[token_id] = {
                "data": token_data,
                "expiry": expiry
            }
        
        # Trigger background cleanup if we have many tokens
        if len(self._tokens) > 100:
            self._trigger_background_eviction()
    
    def invalidate(self, token_id: str) -> bool:
        """Explicitly invalidate/remove a token."""
        with self._lock:
            if token_id in self._tokens:
                del self._tokens[token_id]
                return True
            return False
    
    def _trigger_background_eviction(self):
        """Remove expired tokens to prevent memory leaks."""
        now = datetime.now()
        with self._lock:
            # Create a list of keys to remove to avoid modifying during iteration
            expired_tokens = [tk for tk, data in self._tokens.items() 
                             if data["expiry"] < now]
            
            # Remove expired tokens
            for tk in expired_tokens:
                del self._tokens[tk]
    
    def _background_cleanup(self):
        """Background thread that periodically cleans up expired tokens."""
        while True:
            time.sleep(60)  # Run cleanup every minute
            try:
                self._trigger_background_eviction()
            except Exception as e:
                logging.error(f"Error in token cleanup: {e}")


class AuthenticationService:
    """
    Enterprise Authentication Service.
    Handles user authentication, token generation, and session management.
    """
    
    def __init__(self, origin_id: str = "dt0c01.AUTO_GENERATED"):
        self.origin_id = origin_id
        self.cache = TokenCache(default_ttl_seconds=1800)  # 30 minute default TTL
        
        # Mock user database
        self.users = {
            "user@company.com": {
                "password_hash": "$2b$12$T3jB5Bx2Dw0y5nxX7c8zO.qP5TYpAYSHd.jfV0B0WnHjMOm3A6Fm2",  # UserPass1!
                "roles": ["user", "reports"]
            },
            "admin@company.com": {
                "password_hash": "$2b$12$LZk/d7H4wGF.GA.n.Jbz8e8Bf1XWnM4Tl4C5x3XY7Z0aB1C2D3E4F",  # AdminPass123!
                "roles": ["user", "admin", "reports"]
            }
        }
        
        # Start worker threads
        self.workers = []
        for i in range(3):
            t = threading.Thread(
                target=self._background_worker,
                args=(i,),
                daemon=True
            )
            t.start()
            self.workers.append(t)
    
    def authenticate(self, username: str, password: str, ip_address: str) -> Dict:
        """Authenticate a user and generate a session token."""
        logging.info(f"Authentication attempt for {username} from {ip_address}")
        
        # In a real system, we would verify password hash here
        if username not in self.users:
            error_msg = f"Authentication failed: User {username} not found"
            logging.warning(error_msg)
            return {"status": "error", "message": "Invalid credentials"}
        
        # Generate a new token
        token_id = str(uuid.uuid4())
        token_data = {
            "username": username,
            "roles": self.users[username]["roles"],
            "ip_address": ip_address,
            "created_at": datetime.now().isoformat()
        }
        
        # Store in cache
        self.cache.store_token(
            token_id,
            token_data,
            ttl_seconds=3600  # 1 hour token
        )
        
        return {
            "status": "success",
            "token": token_id,
            "expires_in": 3600,
            "user": {
                "username": username,
                "roles": self.users[username]["roles"]
            }
        }
    
    def validate_token(self, token_id: str, required_roles: Optional[List[str]] = None) -> Dict:
        """Validate a token and check if it has required roles."""
        token_data = self.cache.get_token(token_id)
        
        if not token_data:
            return {"valid": False, "reason": "Token expired or invalid"}
        
        # Check roles if specified
        if required_roles:
            user_roles = set(token_data.get("roles", []))
            if not any(role in user_roles for role in required_roles):
                return {"valid": False, "reason": "Insufficient permissions"}
        
        return {"valid": True, "user": token_data}
    
    def invalidate_token(self, token_id: str) -> Dict:
        """Logout - invalidate a token."""
        success = self.cache.invalidate(token_id)
        return {"status": "success" if success else "error"}
    
    def _background_worker(self, worker_id: int):
        """Background worker that simulates authentication traffic."""
        idp = self  # Identity Provider reference
        
        while True:
            try:
                # Simulate random authentication attempts
                time.sleep(random.uniform(5, 15))
                
                # 80% success, 20% failure simulation
                if random.random() < 0.8:
                    res = idp.authenticate("user@company.com", "UserPass1!", f"192.168.1.{worker_id}")
                    if res["status"] != "success":
                        logging.error(f"Worker {worker_id}: Unexpected auth failure")
                else:
                    # Simulate bad password
                    res = idp.authenticate("user@company.com", "WrongPass!", f"192.168.1.{worker_id}")
                    if res["status"] == "success":
                        logging.error(f"Worker {worker_id}: Security issue - auth succeeded with bad password")
                        
            except Exception as e:
                error_msg = f"CRITICAL FAULT in AuthenticationService._trigger_background_eviction\nUser Context: SYSTEM_WORKER\nException: {str(e)}\nTraceback:\n{traceback.format_exc()}"
                logging.error(error_msg)
                
                # Report to Dynatrace
                log_error_to_dynatrace(
                    error_msg,
                    self.origin_id,
                    app_name="authentication-service"
                )


# For testing/simulation
import traceback

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔐 STARTING AUTHENTICATION SERVICE SIMULATOR")
    print("🔗 Dynatrace Active. Origin ID: dt0c01.AUTH_CLUSTER_998A2B")
    print("="*60)
    
    # Create service with unique origin ID
    auth_service = AuthenticationService(origin_id="dt0c01.AUTH_CLUSTER_998A2B")
    
    # Simulate successful login
    print("\n[Simulation] Login attempt 1 (should succeed)")
    result1 = auth_service.authenticate("user@company.com", "UserPass1!", "192.168.1.100")
    print(f"Login result: {result1['status']}")
    
    if result1["status"] == "success":
        token = result1["token"]
        
        # Validate the token
        print("\n[Simulation] Token validation")
        validation = auth_service.validate_token(token, required_roles=["user"])
        print(f"Token valid: {validation['valid']}")
        
        # Logout
        print("\n[Simulation] Logout")
        logout = auth_service.invalidate_token(token)
        print(f"Logout status: {logout['status']}")
        
        # Try to use invalidated token
        print("\n[Simulation] Using invalidated token")
        revalidation = auth_service.validate_token(token)
        print(f"Token still valid: {revalidation['valid']}")
    
    # Simulate failed login
    print("\n[Simulation] Login attempt 2 (should fail)")
    result2 = auth_service.authenticate("nonexistent@company.com", "WrongPass", "192.168.1.200")
    print(f"Login result: {result2['status']}")
    
    print("\n" + "="*60)
    print("✅ AUTHENTICATION SERVICE SIMULATION COMPLETE")
    print("="*60)
