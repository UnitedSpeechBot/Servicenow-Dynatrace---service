import time
import uuid
import hashlib
import threading
import logging
from typing import Dict, List, Optional, Tuple

class TokenCache:
    """In-memory token cache with TTL-based expiration."""
    
    def __init__(self, ttl_seconds: int = 3600):
        self._tokens = {}  # token -> (expiry_time, user_id)
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
    
    def get_token(self, token: str) -> Optional[str]:
        """Retrieve a token if it exists and is not expired."""
        with self._lock:
            if token not in self._tokens:
                return None
            
            expiry, user_id = self._tokens[token]
            if time.time() > expiry:
                del self._tokens[token]
                return None
                
            return user_id
    
    def store_token(self, token: str, user_id: str) -> None:
        """Store a new token with the current TTL."""
        with self._lock:
            expiry = time.time() + self._ttl
            self._tokens[token] = (expiry, user_id)
            self._trigger_background_eviction()
    
    def revoke_token(self, token: str) -> bool:
        """Explicitly remove a token before its natural expiration."""
        with self._lock:
            if token in self._tokens:
                del self._tokens[token]
                return True
            return False
    
    def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke all tokens belonging to a specific user."""
        count = 0
        with self._lock:
            to_delete = []
            for tk, (_, uid) in self._tokens.items():
                if uid == user_id:
                    to_delete.append(tk)
            
            for tk in to_delete:
                del self._tokens[tk]
                count += 1
                
        return count
    
    def _trigger_background_eviction(self) -> None:
        """Clean up expired tokens if cache is getting large."""
        # Only run cleanup if we have a significant number of tokens
        if len(self._tokens) < 100:
            return
            
        with self._lock:
            now = time.time()
            # Create a copy of the keys to avoid modifying during iteration
            tokens_copy = list(self._tokens.keys())
            for tk in tokens_copy:
                expiry, _ = self._tokens.get(tk, (0, ""))
                if now > expiry:
                    del self._tokens[tk]


class IdentityProvider:
    """Authentication service with token management."""
    
    def __init__(self):
        self.cache = TokenCache(ttl_seconds=1800)  # 30 minute sessions
        self._users = {}  # username -> (password_hash, user_id, role)
        self._failed_attempts = {}  # username -> (count, last_attempt_time)
        self._lockout_threshold = 5
        self._lockout_duration = 300  # 5 minutes
        
        # Add some test users
        self._add_user("admin@company.com", "AdminPass123!", "admin")
        self._add_user("user@company.com", "UserPass1!", "user")
        
    def _add_user(self, username: str, password: str, role: str) -> None:
        """Add a user to the identity store."""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        user_id = str(uuid.uuid4())
        self._users[username] = (password_hash, user_id, role)
    
    def _check_password(self, username: str, password: str) -> bool:
        """Verify a user's password."""
        if username not in self._users:
            return False
            
        stored_hash, _, _ = self._users[username]
        attempt_hash = hashlib.sha256(password.encode()).hexdigest()
        return stored_hash == attempt_hash
    
    def _is_account_locked(self, username: str) -> bool:
        """Check if an account is temporarily locked due to failed attempts."""
        if username not in self._failed_attempts:
            return False
            
        count, last_attempt = self._failed_attempts[username]
        if count >= self._lockout_threshold:
            # Check if lockout period has expired
            if time.time() - last_attempt < self._lockout_duration:
                return True
            else:
                # Reset counter after lockout period
                self._failed_attempts[username] = (0, 0)
                
        return False
    
    def authenticate(self, username: str, password: str, ip_address: str) -> Tuple[bool, Optional[str], str]:
        """Authenticate a user and return a session token if successful."""
        # Check for account lockout
        if self._is_account_locked(username):
            return False, None, "Account temporarily locked due to multiple failed attempts"
        
        # Check if user exists
        if username not in self._users:
            return False, None, "Invalid username or password"
        
        # Verify password
        if not self._check_password(username, password):
            # Track failed attempt
            count, _ = self._failed_attempts.get(username, (0, 0))
            self._failed_attempts[username] = (count + 1, time.time())
            
            return False, None, "Invalid username or password"
        
        # Reset failed attempts on successful login
        if username in self._failed_attempts:
            self._failed_attempts[username] = (0, 0)
        
        # Generate token
        _, user_id, role = self._users[username]
        token = str(uuid.uuid4())
        
        # Store in cache
        self.cache.store_token(
            token=token,
            user_id=user_id
        )
        
        return True, token, role
    
    def validate_token(self, token: str) -> Tuple[bool, Optional[str]]:
        """Validate a token and return the associated user_id if valid."""
        user_id = self.cache.get_token(token)
        if user_id:
            return True, user_id
        return False, None
    
    def logout(self, token: str) -> bool:
        """Invalidate a specific session token."""
        return self.cache.revoke_token(token)
    
    def logout_all_sessions(self, username: str) -> int:
        """Invalidate all sessions for a specific user."""
        if username not in self._users:
            return 0
            
        _, user_id, _ = self._users[username]
        return self.cache.revoke_all_for_user(user_id)


# Demo code to simulate authentication traffic
def worker(worker_id: int, iterations: int = 5):
    """Simulate authentication requests."""
    idp = IdentityProvider()
    
    for i in range(iterations):
        # Simulate successful login
        res = idp.authenticate("user@company.com", "UserPass1!", f"192.168.1.{worker_id}")
        if res[0]:
            token = res[1]
            # Validate token
            valid, user_id = idp.validate_token(token)
            if valid:
                # Logout after some time
                if i % 2 == 0:
                    idp.logout(token)
        
        # Simulate failed login attempt
        if i % 3 == 0:
            idp.authenticate("user@company.com", "WrongPassword", f"192.168.1.{worker_id}")
        
        time.sleep(0.1)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("Starting Authentication Service simulation...")
    
    # Create multiple worker threads to simulate concurrent users
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i, 10))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    print("Authentication Service simulation completed.")
