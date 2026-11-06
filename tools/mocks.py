from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from core.schema import MockPortalResponse

class CIPCPortalMock:
    """Mock portal client for CIPC (Companies and Intellectual Property Commission)."""

    def __init__(self):
        self.registered_companies: Dict[str, Dict[str, Any]] = {
            "2021/890123/07": {
                "business_name": "Batho Beauty & Logistics (Pty) Ltd",
                "status": "In Business",
                "annual_returns_up_to_date": True,
                "registration_date": "2021-04-12",
                "directors": ["8901015000087"]
            }
        }

    def verify_company(self, reg_number: str) -> MockPortalResponse:
        if reg_number in self.registered_companies:
            company = self.registered_companies[reg_number]
            return MockPortalResponse(
                portal_name="CIPC",
                status_code=200,
                success=True,
                data={
                    "registration_number": reg_number,
                    "company_name": company["business_name"],
                    "status": company["status"],
                    "annual_returns_due": not company["annual_returns_up_to_date"]
                }
            )
        return MockPortalResponse(
            portal_name="CIPC",
            status_code=404,
            success=False,
            data={},
            error_message=f"Company registration number {reg_number} not found on CIPC registry."
        )

    def check_name_availability(self, proposed_name: str) -> MockPortalResponse:
        name_clean = proposed_name.strip().upper()
        words = [w for w in name_clean.split() if len(w) > 3]
        is_taken = False
        for company in self.registered_companies.values():
            c_name = company["business_name"].upper()
            if any(w in c_name for w in words):
                is_taken = True
                break

        return MockPortalResponse(
            portal_name="CIPC",
            status_code=200,
            success=True,
            data={
                "proposed_name": proposed_name,
                "available": not is_taken,
                "fee_zar": 175.00,
                "cor14_1_ready": not is_taken
            }
        )

class SARSeFilingMock:
    """Mock portal client for SARS eFiling & Tax Compliance Status (TCS)."""

    def __init__(self):
        self.tcs_pins: Dict[str, Dict[str, Any]] = {
            "9876543210": {
                "tax_number": "9123456789",
                "taxpayer_name": "Batho Beauty & Logistics",
                "status": "Good Standing",
                "expiry_date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
            }
        }

    def validate_tcs_pin(self, tax_number: str, pin: str) -> MockPortalResponse:
        if pin in self.tcs_pins and self.tcs_pins[pin]["tax_number"] == tax_number:
            record = self.tcs_pins[pin]
            return MockPortalResponse(
                portal_name="SARS_eFiling",
                status_code=200,
                success=True,
                data={
                    "tax_number": tax_number,
                    "tcs_pin": pin,
                    "compliance_status": record["status"],
                    "expiry_date": record["expiry_date"],
                    "is_valid": True
                }
            )
        return MockPortalResponse(
            portal_name="SARS_eFiling",
            status_code=400,
            success=False,
            data={"is_valid": False},
            error_message="Invalid TCS PIN or tax number mismatch."
        )

    def request_fresh_tcs_pin(self, tax_number: str) -> MockPortalResponse:
        new_pin = f"99{datetime.now().strftime('%M%S%f')[:8]}"
        new_expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        
        self.tcs_pins[new_pin] = {
            "tax_number": tax_number,
            "taxpayer_name": "Batho Beauty & Logistics",
            "status": "Good Standing",
            "expiry_date": new_expiry
        }

        return MockPortalResponse(
            portal_name="SARS_eFiling",
            status_code=200,
            success=True,
            data={
                "tax_number": tax_number,
                "tcs_pin": new_pin,
                "status": "Good Standing",
                "issued_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "expiry_date": new_expiry,
                "validity_days": 365
            }
        )

    def calculate_provisional_tax(self, annual_turnover: float, expenses: float) -> MockPortalResponse:
        taxable_income = max(0.0, annual_turnover - expenses)
        if taxable_income <= 95750:
            tax_due = 0.0
        elif taxable_income <= 365000:
            tax_due = (taxable_income - 95750) * 0.07
        else:
            tax_due = 18848 + (taxable_income - 365000) * 0.21

        return MockPortalResponse(
            portal_name="SARS_eFiling",
            status_code=200,
            success=True,
            data={
                "turnover": annual_turnover,
                "expenses": expenses,
                "taxable_income": taxable_income,
                "estimated_provisional_tax_zar": round(tax_due, 2),
                "tax_year": "2026"
            }
        )

class CSDPortalMock:
    """Mock portal client for National Treasury Central Supplier Database (CSD)."""

    def __init__(self):
        self.suppliers: Dict[str, Dict[str, Any]] = {
            "MAAA0123456": {
                "supplier_name": "Batho Beauty & Logistics",
                "status": "Active",
                "tax_compliant": True,
                "tcs_pin": "9876543210",
                "bbbee_level": 1,
                "bank_verified": True,
                "last_updated": (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
            }
        }

    def get_supplier_status(self, csd_number: str) -> MockPortalResponse:
        if csd_number in self.suppliers:
            supplier = self.suppliers[csd_number]
            return MockPortalResponse(
                portal_name="CSD",
                status_code=200,
                success=True,
                data={
                    "csd_number": csd_number,
                    "supplier_name": supplier["supplier_name"],
                    "status": supplier["status"],
                    "tax_compliant": supplier["tax_compliant"],
                    "bbbee_level": supplier["bbbee_level"],
                    "bank_verified": supplier["bank_verified"],
                    "ready_for_tender": supplier["status"] == "Active" and supplier["tax_compliant"]
                }
            )
        return MockPortalResponse(
            portal_name="CSD",
            status_code=404,
            success=False,
            data={},
            error_message=f"CSD Supplier Number {csd_number} not found."
        )

    def refresh_csd_tax_status(self, csd_number: str, fresh_tcs_pin: str) -> MockPortalResponse:
        if csd_number in self.suppliers:
            self.suppliers[csd_number]["tcs_pin"] = fresh_tcs_pin
            self.suppliers[csd_number]["tax_compliant"] = True
            self.suppliers[csd_number]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            return MockPortalResponse(
                portal_name="CSD",
                status_code=200,
                success=True,
                data={
                    "csd_number": csd_number,
                    "updated_tcs_pin": fresh_tcs_pin,
                    "tax_compliance_synced": True,
                    "timestamp": datetime.now().isoformat()
                }
            )
        return MockPortalResponse(
            portal_name="CSD",
            status_code=404,
            success=False,
            data={},
            error_message=f"CSD Supplier Number {csd_number} not found."
        )