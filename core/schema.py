import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ComplianceStatus(BaseModel):
    csd_registered: bool = True
    csd_number: str = "MAAA0123456"
    csd_expiry_days: int = 5
    tax_compliant: bool = True
    tcs_pin: str = "9876543210"
    tcs_pin_expiry_days: int = 2
    bbbee_level: int = 1
    bbbee_affidavit_valid: bool = True
    coida_valid: bool = False
    cipc_annual_returns_due: bool = False

class FinancialOverview(BaseModel):
    rolling_revenue_12m: float = 245000.00
    estimated_vat_due: float = 0.0  # Below R1M threshold
    provisional_tax_estimate: float = 14200.00
    last_receipt_logged: Optional[str] = "2026-10-25"
    bank_account_verified: bool = True

class TenderOpportunity(BaseModel):
    id: str
    title: str
    issuer: str
    value: str
    closing_date: str
    required_docs: List[str]

class EncryptedCredential(BaseModel):
    service_name: str
    ciphertext: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    key_fingerprint: str

class AuditLogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    action: str
    actor_id: str
    resource_accessed: str
    popia_purpose: str
    status: str = "SUCCESS"

class MockPortalResponse(BaseModel):
    portal_name: str
    status_code: int
    success: bool
    data: Dict[str, Any]
    error_message: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class SMMEProfile(BaseModel):
    business_name: str = "Batho Beauty & Logistics"
    registration_number: str = "2021/890123/07"
    owner_name: str = "Nandi Mokwena"
    owner_id_number: str = "8901015000087"
    location: str = "Batho, Bloemfontein"
    compliance: ComplianceStatus = Field(default_factory=ComplianceStatus)
    financials: FinancialOverview = Field(default_factory=FinancialOverview)