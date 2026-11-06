import os
import sys
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.schema import SMMEProfile
from core.crypto import POPIADataMasker, POPIAAuditLogger
from tools.tender_tools import GovernanceTenderTools
from tools.tax_tools import TaxFinancialTools
from agents.gemini_client import GeminiClient
from agents.adk_agent import root_agent, tender_governance_agent, tax_financial_agent

class ModularADKOrchestrator:
    """Master Orchestrator coordinating ADK Agent execution, modular tools, and POPIA auditing."""

    def __init__(self, api_key: Optional[str] = None):
        self.gemini_client = GeminiClient(api_key=api_key)
        self.tender_tools = GovernanceTenderTools()
        self.tax_tools = TaxFinancialTools()
        self.audit_logger = POPIAAuditLogger()

    def process_user_query(self, user_message: str, profile: SMMEProfile, target_tender_id: Optional[str] = None) -> Dict[str, Any]:
        sanitized_input = POPIADataMasker.sanitize_prompt_text(user_message)
        self.audit_logger.log_access(
            action="ADK_AGENT_INFERENCE_START",
            actor_id=profile.owner_name,
            resource="ADKRootAgent",
            purpose="Analyze  query via ADK agent"
        )

        profile_summary = f"Business: {profile.business_name}, CSD: {profile.compliance.csd_number}, Tax PIN: {profile.compliance.tcs_pin}"
        decision = self.gemini_client.parse_gemini_response(sanitized_input, profile_summary)

        delegated_agent = decision.get("agent_name", "MasterOrchestrator")
        actions_taken = []
        response_text = ""

        tool_name = decision.get("tool_name")
        args = decision.get("args", {})

        if tool_name == "refresh_sars_tcs":
            delegated_agent = "Agent1_TenderGovernance (ADK)"
            self.audit_logger.log_access("TOOL_EXECUTION", profile.owner_name, "Tool:refresh_sars_tcs", "Refresh SARS TCS PIN")

            res = self.tender_tools.refresh_sars_tcs("9123456789", csd_number=profile.compliance.csd_number)
            new_pin = res["new_tcs_pin"]
            expiry = res["expiry_date"]

            profile.compliance.tcs_pin = new_pin
            profile.compliance.tcs_pin_expiry_days = 365
            profile.compliance.tax_compliant = True

            masked_pin = POPIADataMasker.mask_tcs_pin(new_pin)
            response_text = (
                f"Molo {profile.owner_name}! The Tender & Governance Agent issued a fresh SARS Tax Compliance Status (TCS) PIN: "
                f"**{masked_pin}** (Valid for 365 days until {expiry}). "
                f"CSD profile ({profile.compliance.csd_number}) has been updated automatically."
            )
            actions_taken.append("ADK Agent Invoked: Refreshed SARS TCS PIN & Synced with CSD")

        elif tool_name == "generate_tender_pack":
            delegated_agent = "Agent1_TenderGovernance (ADK)"
            self.audit_logger.log_access("TOOL_EXECUTION", profile.owner_name, "Tool:generate_tender_pack", "Assemble MBD Forms")

            t_id = target_tender_id or args.get("tender_id", "MMM-2026-C04")
            pack = self.tender_tools.generate_tender_pack(
                profile,
                tender_id=t_id,
                tender_title=args.get("tender_title", "Catering & Event Services"),
                issuer=args.get("issuer", "Mangaung Metropolitan Municipality")
            )

            status_str = "SUBMISSION READY (100%)" if pack["is_submission_ready"] else f"READINESS: {pack['readiness_percentage']}%"
            response_text = (
                f"Great news, {profile.owner_name}! The Tender & Governance Agent generated your application pack for **{t_id}**.\\n\\n"
                f"📋 **Status**: {status_str}\\n"
                f"• Generated **MBD 4** (Declaration of Interest)\\n"
                f"• Generated **MBD 6.1** (B-BBEE Preference Points Form - Level {profile.compliance.bbbee_level})\\n"
                f"• Verified active CSD & Tax Compliance PIN"
            )
            actions_taken.append(f"ADK Agent Invoked: Generated Municipal Tender Pack (MBD 4 & 6.1) for {t_id}")

        elif tool_name == "log_transaction":
            delegated_agent = "Agent2_TaxFinancials (ADK)"
            self.audit_logger.log_access("TOOL_EXECUTION", profile.owner_name, "Tool:log_transaction", "Log Financial Sale")

            amt = args.get("amount", 500.0)
            res = self.tax_tools.log_transaction(profile, description=user_message, amount=amt, is_income=True)

            response_text = (
                f"Logged transaction of **R{amt:,.2f}**. "
                f"Your 12-month rolling revenue is now **R{profile.financials.rolling_revenue_12m:,.2f}**.\\n\\n"
                f"📊 **Financial Insights**:\\n"
                f"• Estimated SARS Provisional Tax: R{profile.financials.provisional_tax_estimate:,.2f}\\n"
                f"• Compulsory VAT Threshold: {res['updated_financials']['vat_compulsory_threshold_pct']}% of R1M reached."
            )
            actions_taken.append(f"ADK Agent Invoked: Logged transaction R{amt} & updated tax estimate")

        elif tool_name == "evaluate_capital_eligibility":
            delegated_agent = "MasterOrchestrator (ADK)"
            self.audit_logger.log_access("TOOL_EXECUTION", profile.owner_name, "Tool:evaluate_capital_eligibility", "Evaluate SEFA Funding")

            cap_res = self.tax_tools.evaluate_capital_eligibility(profile)
            sefa = cap_res["sefa_microloan"]

            if sefa["eligible"]:
                response_text = (
                    f"Awesome news, {profile.owner_name}! Based on your revenue of R{profile.financials.rolling_revenue_12m:,.2f}, "
                    f"you pre-qualify for a **SEFA Micro-loan up to R{sefa['estimated_max_amount_zar']:,.2f}**.\\n"
                    f"Purchase Order funding is also active for compliant municipal tenders."
                )
            else:
                response_text = "You are close to unlocking funding! Ensure your tax compliance PIN and CSD profile are active."
            actions_taken.append("ADK Agent Invoked: Evaluated SEFA Micro-loan eligibility")

        else:
            response_text = decision.get("text", f"Molo {profile.owner_name}! I am your ADK-powered Compliance Orchestrator.")
            actions_taken.append("ADK Agent Conversational Guidance")

        self.audit_logger.log_access("ADK_AGENT_INFERENCE_FINISH", profile.owner_name, "ADKRootAgent", "Completed response processing")

        return {
            "delegated_agent": delegated_agent,
            "response_text": response_text,
            "actions_taken": actions_taken,
            "model_used": decision.get("model_name", "gemini-2.5-flash"),
            "updated_profile": profile,
            "audit_logs": [log.model_dump() for log in self.audit_logger.logs]
        }
      