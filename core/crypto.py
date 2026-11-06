import re
import hashlib
from datetime import datetime
from typing import List, Optional
from cryptography.fernet import Fernet
from core.schema import EncryptedCredential, AuditLogEntry

class SMMEKeyManager:
    """Manages symmetric key generation and key fingerprints for credential encryption."""
    
    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode('utf-8')
    
    @staticmethod
    def get_key_fingerprint(key_str: str) -> str:
        return hashlib.sha256(key_str.encode('utf-8')).hexdigest()[:12]

class CredentialEncryptor:
    """Encrypts and decrypts sensitive government credentials (SARS, CSD, CIPC)."""

    def __init__(self, key_str: Optional[str] = None):
        if key_str:
            self.key_bytes = key_str.encode('utf-8')
        else:
            self.key_bytes = Fernet.generate_key()
        self.fernet = Fernet(self.key_bytes)
        self.key_str = self.key_bytes.decode('utf-8')
        self.fingerprint = SMMEKeyManager.get_key_fingerprint(self.key_str)

    def encrypt(self, service_name: str, secret_text: str) -> EncryptedCredential:
        cipher_bytes = self.fernet.encrypt(secret_text.encode('utf-8'))
        return EncryptedCredential(
            service_name=service_name,
            ciphertext=cipher_bytes.decode('utf-8'),
            key_fingerprint=self.fingerprint
        )

    def decrypt(self, credential: EncryptedCredential) -> str:
        if credential.key_fingerprint != self.fingerprint:
            raise ValueError("Key fingerprint mismatch: Cannot decrypt with current key.")
        decrypted_bytes = self.fernet.decrypt(credential.ciphertext.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')

class POPIADataMasker:
    """Utility functions for masking PII to comply with South Africa's POPI Act."""

    @staticmethod
    def mask_id_number(id_number: str) -> str:
        clean_id = id_number.strip()
        if len(clean_id) == 13 and clean_id.isdigit():
            return f"{clean_id[:6]}*****{clean_id[11:]}"
        return "*****"

    @staticmethod
    def mask_tcs_pin(pin: str) -> str:
        clean_pin = pin.strip()
        if len(clean_pin) >= 8:
            return f"{clean_pin[:4]}****{clean_pin[-2:]}"
        return "****"

    @staticmethod
    def mask_bank_account(acc_num: str) -> str:
        clean_acc = acc_num.strip()
        if len(clean_acc) >= 6:
            return "*" * (len(clean_acc) - 4) + clean_acc[-4:]
        return "****"

    @staticmethod
    def sanitize_prompt_text(text: str) -> str:
        sanitized = re.sub(r'\b\d{13}\b', '[REDACTED_SA_ID]', text)
        sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]', sanitized)
        sanitized = re.sub(r'\b(0\d{9}|\+27\d{9})\b', '[REDACTED_PHONE]', sanitized)
        return sanitized

class POPIAAuditLogger:
    """In-memory audit log manager for tracking PII access for regulatory audits."""

    def __init__(self):
        self.logs: List[AuditLogEntry] = []

    def log_access(self, action: str, actor_id: str, resource: str, purpose: str, status: str = "SUCCESS") -> AuditLogEntry:
        entry = AuditLogEntry(
            action=action,
            actor_id=actor_id,
            resource_accessed=resource,
            popia_purpose=purpose,
            status=status
        )
        self.logs.append(entry)
        return entry

    def get_logs_for_actor(self, actor_id: str) -> List[AuditLogEntry]:
        return [log for log in self.logs if log.actor_id == actor_id]