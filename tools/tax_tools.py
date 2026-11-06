from datetime import datetime
from typing import Dict, Any
from core.schema import SMMEProfile
from tools.mocks import SARSeFilingMock

class TaxFinancialTools:
    """Tools executable by Agent 2 (Tax & Financial Readiness Agent)."""

    def __init__(self):
        self.sars_mock = SARSeFilingMock()

    def log_transaction(self, profile: SMMEProfile, description: str, amount: float, is_income: bool = True) -> Dict[str, Any]:
        if is_income:
            profile.financials.rolling_revenue_12m += amount
        profile.financials.last_receipt_logged = datetime.now().strftime("%Y-%m-%d")

        tax_resp = self.sars_mock.calculate_provisional_tax(
            profile.financials.rolling_revenue_12m,
            expenses=profile.financials.rolling_revenue_12m * 0.40
        )
        profile.financials.provisional_tax_estimate = tax_resp.data["estimated_provisional_tax_zar"]

        return {
            "transaction_logged": {
                "description": description,
                "amount_zar": amount,
                "type": "INCOME" if is_income else "EXPENSE",
                "timestamp": datetime.now().isoformat()
            },
            "updated_financials": {
                "rolling_revenue_12m": profile.financials.rolling_revenue_12m,
                "provisional_tax_estimate": profile.financials.provisional_tax_estimate,
                "vat_compulsory_threshold_pct": min(100, int((profile.financials.rolling_revenue_12m / 1000000.0) * 100))
            }
        }

    def evaluate_capital_eligibility(self, profile: SMMEProfile) -> Dict[str, Any]:
        rev = profile.financials.rolling_revenue_12m
        is_compliant = profile.compliance.tax_compliant and profile.compliance.csd_registered

        sefa_eligible = is_compliant and rev >= 50000.0
        sefa_max_loan = 0.0
        if sefa_eligible:
            sefa_max_loan = min(250000.0, max(20000.0, rev * 0.5))

        po_funding_eligible = is_compliant and profile.compliance.bbbee_affidavit_valid

        return {
            "sefa_microloan": {
                "eligible": sefa_eligible,
                "estimated_max_amount_zar": sefa_max_loan,
                "requirements_met": ["Tax Compliant", "CSD Active", "Revenue > R50k"] if sefa_eligible else ["Requires Tax Compliance & Active CSD"]
            },
            "po_funding": {
                "eligible": po_funding_eligible,
                "max_coverage_pct": 100 if po_funding_eligible else 0,
                "status": "Ready for Purchase Order Backing" if po_funding_eligible else "Pending B-BBEE & Tax Clearance"
            }
        }