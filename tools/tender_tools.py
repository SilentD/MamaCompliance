from datetime import datetime
from typing import Dict, Any, Optional
from core.schema import SMMEProfile, MockPortalResponse
from core.crypto import POPIADataMasker
from tools.mocks import CIPCPortalMock, SARSeFilingMock, CSDPortalMock

class MBDFormGenerator:
    """Generates South African Municipal Bidding Documents (MBD 4 & MBD 6.1)."""

    @staticmethod
    def generate_mbd4(profile: SMMEProfile, tender_id: str, issuer: str) -> Dict[str, Any]:
        return {
            "form_code": "MBD 4",
            "title": "Declaration of Interest",
            "tender_id": tender_id,
            "issuer": issuer,
            "company_name": profile.business_name,
            "registration_number": profile.registration_number,
            "owner_name": profile.owner_name,
            "owner_id_masked": POPIADataMasker.mask_id_number(profile.owner_id_number),
            "tax_number_verified": profile.compliance.tax_compliant,
            "tcs_pin_masked": POPIADataMasker.mask_tcs_pin(profile.compliance.tcs_pin),
            "state_employed_declaration": False,
            "declaration_statement": (
                f"I, {profile.owner_name}, hereby certify that the information provided in this MBD 4 declaration "
                f"for {profile.business_name} ({profile.registration_number}) is complete, true, and compliant with Municipal SCM Regulations."
            ),
            "generated_at": datetime.now().isoformat()
        }

    @staticmethod
    def generate_mbd6_1(profile: SMMEProfile, tender_id: str, tender_value_estimate: float) -> Dict[str, Any]:
        system = "80/20" if tender_value_estimate <= 5000000.0 else "90/10"
        points_map = {1: 20, 2: 18, 3: 14, 4: 12, 5: 8, 6: 6, 7: 4, 8: 2}
        bbee_points = points_map.get(profile.compliance.bbbee_level, 20)

        return {
            "form_code": "MBD 6.1",
            "title": "Preference Points Claim Form in Terms of Preferential Procurement Regulations",
            "tender_id": tender_id,
            "preference_system": system,
            "bbbee_level": profile.compliance.bbbee_level,
            "claimed_bbbee_points": bbee_points,
            "sworn_affidavit_attached": profile.compliance.bbbee_affidavit_valid,
            "csd_number": profile.compliance.csd_number,
            "generated_at": datetime.now().isoformat()
        }

class GovernanceTenderTools:
    """Tools executable by Agent 1 (Tender & Governance Agent)."""

    def __init__(self):
        self.sars_mock = SARSeFilingMock()
        self.csd_mock = CSDPortalMock()
        self.cipc_mock = CIPCPortalMock()

    def refresh_sars_tcs(self, tax_number: str, csd_number: Optional[str] = None) -> Dict[str, Any]:
        tcs_resp = self.sars_mock.request_fresh_tcs_pin(tax_number)
        csd_synced = False
        if tcs_resp.success and csd_number:
            new_pin = tcs_resp.data["tcs_pin"]
            csd_resp = self.csd_mock.refresh_csd_tax_status(csd_number, new_pin)
            csd_synced = csd_resp.success

        return {
            "tcs_response": tcs_resp.model_dump(),
            "csd_synced": csd_synced,
            "new_tcs_pin": tcs_resp.data.get("tcs_pin"),
            "expiry_date": tcs_resp.data.get("expiry_date")
        }

    def check_csd_status(self, csd_number: str) -> MockPortalResponse:
        return self.csd_mock.get_supplier_status(csd_number)

    def verify_cipc(self, reg_number: str) -> MockPortalResponse:
        return self.cipc_mock.verify_company(reg_number)

    def generate_tender_pack(self, profile: SMMEProfile, tender_id: str, tender_title: str, issuer: str, estimated_value: float = 150000.0) -> Dict[str, Any]:
        mbd4 = MBDFormGenerator.generate_mbd4(profile, tender_id, issuer)
        mbd6_1 = MBDFormGenerator.generate_mbd6_1(profile, tender_id, estimated_value)

        readiness_items = [
            {"doc": "CSD Registration Summary", "status": "READY" if profile.compliance.csd_registered else "MISSING"},
            {"doc": "SARS Tax Compliance PIN", "status": "READY" if profile.compliance.tax_compliant else "EXPIRED"},
            {"doc": "B-BBEE Sworn Affidavit", "status": "READY" if profile.compliance.bbbee_affidavit_valid else "MISSING"},
            {"doc": "COIDA Letter of Good Standing", "status": "READY" if profile.compliance.coida_valid else "ACTION_REQUIRED"},
            {"doc": "MBD 4 Declaration of Interest", "status": "GENERATED"},
            {"doc": "MBD 6.1 Preference Points Form", "status": "GENERATED"}
        ]

        ready_count = sum(1 for item in readiness_items if item["status"] in ["READY", "GENERATED"])
        readiness_pct = int((ready_count / len(readiness_items)) * 100)

        return {
            "tender_id": tender_id,
            "tender_title": tender_title,
            "issuer": issuer,
            "readiness_percentage": readiness_pct,
            "is_submission_ready": readiness_pct >= 80,
            "mbd4_form": mbd4,
            "mbd6_1_form": mbd6_1,
            "compliance_checklist": readiness_items,
            "generated_at": datetime.now().isoformat()
        }