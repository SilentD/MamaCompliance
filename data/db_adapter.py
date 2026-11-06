import os
import json
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.schema import SMMEProfile, AuditLogEntry
from core.auth import AuthManager

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

try:
    from pymongo  import MongoClient
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


class LocalJSONStore:
    """Fallback file-backed document store for offline testing and local execution."""

    def __init__(self, filepath: str = "/local_db.json"):
        self.filepath = filepath
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.filepath):
            data = {
                "users": {},
                "smme_profiles": {},
                "chat_sessions": {},
                "audit_logs": {}
            }
            try:
                os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
                with open(self.filepath, "w") as f:
                    json.dump(data, f)
            except Exception:
                pass

    def _read_data(self) -> Dict[str, Any]:
        self._ensure_file()
        try:
            with open(self.filepath, "r") as f:
                return json.load(f)
        except Exception:
            return {"users": {}, "smme_profiles": {}, "chat_sessions": {}, "audit_logs": {}}

    def _write_data(self, data: Dict[str, Any]):
        try:
            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass


class MongoDBAdapter:
    """MongoDB persistence adapter with secrets discovery and local fallback."""

    def __init__(self, mongo_uri: Optional[str] = None, db_name: str = "smme_compliance_db"):
        self.db_name = db_name
        self.mongo_uri = self._resolve_mongo_uri(mongo_uri)
        self.client = None
        self.db = None
        self.is_connected = False
        self.connection_error = None
        self.local_store = LocalJSONStore()

        self._connect()

    def _resolve_mongo_uri(self, uri: Optional[str] = None) -> Optional[str]:
        if uri:
            return uri
        
        # Check environment variables
        env_uri = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI")
        if env_uri:
            return env_uri

        # Check Streamlit Secrets if available
        if HAS_STREAMLIT:
            try:
                sec_uri = st.secrets["MONGO_URI"] or st.secrets["MONGODB_URI"]
                if sec_uri:
                    return sec_uri
                if "mongo" in st.secrets and isinstance(st.secrets["mongo"], dict):
                    return st.secrets["mongo"].get("uri")
            except Exception:
                pass

        return None

    def _connect(self):
        if HAS_PYMONGO and self.mongo_uri:
            try:
                self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=3000)
                self.client.admin.command('ping')
                self.db = self.client[self.db_name]
                self.is_connected = True
                self.connection_error = None
            except Exception as e:
                self.is_connected = False
                self.connection_error = str(e)
        else:
            self.is_connected = False
            if not HAS_PYMONGO:
                self.connection_error = "PyMongo package not installed."
            elif not self.mongo_uri:
                self.connection_error = "No MONGO_URI provided in environment or secrets."

    def reconnect(self, new_uri: str) -> bool:
        """Attempt to reconnect with a new URI."""
        self.mongo_uri = new_uri
        self._connect()
        return self.is_connected

    def get_status_info(self) -> Dict[str, Any]:
        """Return human-readable connection status."""
        if self.is_connected:
            return {
                "connected": True,
                "type": "MongoDB Atlas Cluster",
                "database": self.db_name,
                "message": "Connected & Syncing Live"
            }
        else:
            return {
                "connected": False,
                "type": "Local JSON Store (Fallback)",
                "database": "local_db.json",
                "message": f"Offline mode: {self.connection_error}"
            }

    def register_user(self, email: str, password: str, business_name: str = "My SMME") -> Dict[str, Any]:
        """Register a new user and initialize their SMME profile."""
        clean_email = email.strip().lower()
        pass_data = AuthManager.hash_password(password)
        import secrets
        user_salt = secrets.token_hex(16)
        user_id = f"usr_{clean_email.replace('@', '_').replace('.', '_')}"

        user_doc = {
            "user_id": user_id,
            "email": clean_email,
            "password_hash": pass_data["hash"],
            "salt": pass_data["salt"],
            "fernet_salt": user_salt,
            "business_name": business_name,
            "created_at": datetime.now().isoformat()
        }

        if self.is_connected:
            self.db.users.update_one({"email": clean_email}, {"$set": user_doc}, upsert=True)
        else:
            data = self.local_store._read_data()
            data["users"][clean_email] = user_doc
            self.local_store._write_data(data)

        # Initialize default profile
        profile = SMMEProfile(business_name=business_name)
        self.save_smme_profile(user_id, profile)

        return user_doc

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user against saved password hash."""
        clean_email = email.strip().lower()
        user_doc = None

        if self.is_connected:
            user_doc = self.db.users.find_one({"email": clean_email})
        else:
            data = self.local_store._read_data()
            user_doc = data["users"].get(clean_email)

        if not user_doc:
            return None

        if AuthManager.verify_password(password, user_doc["password_hash"], user_doc["salt"]):
            return user_doc
        return None

    def save_smme_profile(self, user_id: str, profile: SMMEProfile) -> bool:
        """Persist user SMME profile state."""
        doc = {
            "user_id": user_id,
            "profile_data": profile.model_dump(),
            "updated_at": datetime.now().isoformat()
        }

        if self.is_connected:
            self.db.smme_profiles.update_one({"user_id": user_id}, {"$set": doc}, upsert=True)
        else:
            data = self.local_store._read_data()
            data["smme_profiles"][user_id] = doc
            self.local_store._write_data(data)

        return True

    def get_smme_profile(self, user_id: str) -> SMMEProfile:
        """Fetch saved SMME profile for user."""
        doc = None
        if self.is_connected:
            doc = self.db.smme_profiles.find_one({"user_id": user_id})
        else:
            data = self.local_store._read_data()
            doc = data["smme_profiles"].get(user_id)

        if doc and "profile_data" in doc:
            return SMMEProfile(**doc["profile_data"])
        return SMMEProfile()

    def save_chat_message(self, user_id: str, session_id: str, role: str, agent: str, content: str):
        """Append chat message to session history."""
        msg = {
            "role": role,
            "agent": agent,
            "content": content,
            "timestamp": datetime.now().strftime("%H:%M")
        }

        key = f"{user_id}:{session_id}"
        if self.is_connected:
            self.db.chat_sessions.update_one(
                {"session_key": key},
                {"$push": {"messages": msg}, "$set": {"updated_at": datetime.now().isoformat()}},
                upsert=True
            )
        else:
            data = self.local_store._read_data()
            if key not in data["chat_sessions"]:
                data["chat_sessions"][key] = {"session_key": key, "messages": []}
            data["chat_sessions"][key]["messages"].append(msg)
            self.local_store._write_data(data)

    def get_chat_history(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        """Fetch chat session history."""
        key = f"{user_id}:{session_id}"
        if self.is_connected:
            doc = self.db.chat_sessions.find_one({"session_key": key})
            return doc.get("messages", []) if doc else []
        else:
            data = self.local_store._read_data()
            doc = data["chat_sessions"].get(key)
            return doc.get("messages", []) if doc else []

    def save_audit_logs(self, user_id: str, logs: List[Dict[str, Any]]):
        """Save POPIA data access audit log entries."""
        if not logs:
            return
        if self.is_connected:
            self.db.audit_logs.insert_many([{"user_id": user_id, **log} for log in logs])
        else:
            data = self.local_store._read_data()
            if user_id not in data["audit_logs"]:
                data["audit_logs"][user_id] = []
            data["audit_logs"][user_id].extend(logs)
            self.local_store._write_data(data)