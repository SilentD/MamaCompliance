import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt

JWT_SECRET = os.environ.get("JWT_SECRET", "smme_compliance_secure_jwt_secret_key_32bytes_min")

class AuthManager:
    """Manages user authentication, PBKDF2 password hashing, JWT sessions, and per-user encryption keys."""

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
        """Hash a password using PBKDF2 HMAC SHA-256 with 100,000 iterations."""
        if not salt:
            salt_bytes = secrets.token_bytes(16)
            salt = salt_bytes.hex()
        else:
            salt_bytes = bytes.fromhex(salt)

        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt_bytes,
            100000
        )
        return {
            "hash": key.hex(),
            "salt": salt
        }

    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        """Verify password against saved hash and salt."""
        computed = AuthManager.hash_password(password, salt)
        return hmac.compare_digest(computed["hash"], password_hash)

    @staticmethod
    def create_session_token(user_id: str, email: str, expires_in_hours: int = 24) -> str:
        """Issue signed JWT session token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "email": email,
            "exp": now + timedelta(hours=expires_in_hours),
            "iat": now
        }
        return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    @staticmethod
    def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT session token."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return payload
        except Exception:
            return None

    @staticmethod
    def derive_user_fernet_key(user_id: str, user_salt: str) -> str:
        """Derive a deterministic 32-byte Fernet key for per-user credential encryption."""
        key = hashlib.pbkdf2_hmac(
            'sha256',
            f"{user_id}:{user_salt}".encode('utf-8'),
            user_salt.encode('utf-8'),
            50000
        )
        import base64
        return base64.urlsafe_b64encode(key[:32]).decode('utf-8')