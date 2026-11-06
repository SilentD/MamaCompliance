import os
import sys
import json
import requests
from typing import Dict, Any, List, Optional

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

from agents.prompts import AgentPrompts
from tools.tender_tools import GovernanceTenderTools
from tools.tax_tools import TaxFinancialTools

_tender_tools = GovernanceTenderTools()
_tax_tools = TaxFinancialTools()

class ADKAgent:
    """ADK Agent supporting Groq HTTP inference and resilient fallback."""

    def __init__(
        self,
        name: str,
        model: str = "openai/gpt-oss-120b",
        instructions: str = "",
        description: str = "",
        tools: Optional[List[Any]] = None,
        api_key: Optional[str] = None
    ):
        self.name = name
        self.model = model
        self.instructions = instructions
        self.description = description
        self.tools = tools or []
        
        # Resolve API Key securely
        key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key and HAS_STREAMLIT:
            try:
                key = st.secrets.get("GROQ_API_KEY") or st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
            except Exception:
                key = None
        self.api_key = key

    def run(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute agent reasoning via Groq HTTP API if key is available, else fallback to dispatcher."""
        if self.api_key:
            res = self._call_groq_api(prompt, context)
            if res:
                return res

        return self._run_adk_dispatcher(prompt, context)

    def _call_groq_api(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Call Groq API with live telemetry tracking and structured response parsing."""
        groq_url = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_content = f"{self.instructions}\n\nYou have access to the following tools:\n"
        system_content += "1. refresh_sars_tcs(tax_number, csd_number): Issue fresh 365-day SARS TCS PIN and sync with CSD.\n"
        system_content += "2. generate_tender_pack(tender_id, tender_title, issuer): Pre-fill MBD 4 & 6.1 forms for municipal tender.\n"
        system_content += "3. log_transaction(description, amount, is_income): Record sale/expense receipt into micro-ledger.\n"
        system_content += "4. evaluate_capital_eligibility(): Evaluate pre-qualification for SEFA micro-loans and PO funding.\n\n"
        system_content += "If the query requires executing a tool, respond ONLY in valid JSON format: {\"tool_name\": \"<name>\", \"args\": {<arguments>}}.\n"
        system_content += "If no tool is required, answer conversationally with clear, helpful guidance."

        messages = [{"role": "system", "content": system_content}]
        if context:
            messages.append({"role": "system", "content": f"Business Profile Context: {json.dumps(context)}"})
        messages.append({"role": "user", "content": prompt})

        model_to_use = self.model
        if "openai" in model_to_use.lower():
            model_to_use = "openai/gpt-oss-120b"

        payload = {
            "model": model_to_use,
            "messages": messages,
            "temperature": 0.4
        }

        try:
            response = requests.post(groq_url, headers=headers, json=payload, timeout=45.0)
            
            # Telemetry tracking
            if HAS_STREAMLIT:
                rem_req = response.headers.get("x-ratelimit-remaining-requests")
                rem_tok = response.headers.get("x-ratelimit-remaining-tokens")
                if rem_req:
                    st.sidebar.metric("Remaining Requests Today", rem_req)
                if rem_tok:
                    st.sidebar.metric("Remaining Tokens", rem_tok)

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"].get("content", "").strip()

                if content.startswith("{") and content.endswith("}"):
                    try:
                        parsed = json.loads(content)
                        if "tool_name" in parsed:
                            return {
                                "agent_name": self.name,
                                "has_tool_call": True,
                                "tool_name": parsed["tool_name"],
                                "tool_args": parsed.get("args", {}),
                                "text": f"Agent '{self.name}' invoked {parsed['tool_name']}.",
                                "model": model_to_use,
                                "status": "TOOL_CALL_REQUIRED"
                            }
                    except json.JSONDecodeError:
                        pass

                return {
                    "agent_name": self.name,
                    "has_tool_call": False,
                    "tool_name": None,
                    "tool_args": {},
                    "text": content,
                    "model": model_to_use,
                    "status": "TEXT_RESPONSE"
                }
            elif response.status_code == 429:
                retry_after = response.headers.get("retry-after", "a few")
                if HAS_STREAMLIT:
                    st.sidebar.warning(f"Groq Rate Limit hit. Cooldown: {retry_after}s")
                return None
            else:
                return None
        except Exception as e:
            return {"Error": "Failed to connect AI"}

    def _run_adk_dispatcher(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        prompt_lower = prompt.lower()

        if any(k in prompt_lower for k in ["tax pin", "tcs pin", "tax compliance", "refresh pin", "refresh tcs", "sars pin", "renew pin"]):
            return {
                "agent_name": self.name,
                "has_tool_call": True,
                "tool_name": "refresh_sars_tcs",
                "tool_args": {"tax_number": "9123456789", "csd_number": "MAAA0123456"},
                "text": f"ADK Agent '{self.name}' invoked refresh_sars_tcs tool.",
                "model": self.model,
                "status": "TOOL_CALL_REQUIRED"
            }
        elif any(k in prompt_lower for k in ["tender", "mbd", "catering", "mangaung", "bid pack", "apply for tender"]):
            return {
                "agent_name": self.name,
                "has_tool_call": True,
                "tool_name": "generate_tender_pack",
                "tool_args": {
                    "tender_id": "MMM-2026-C04",
                    "tender_title": "Supply & Delivery of Catering Services",
                    "issuer": "Mangaung Metropolitan Municipality"
                },
                "text": f"ADK Agent '{self.name}' invoked generate_tender_pack tool.",
                "model": self.model,
                "status": "TOOL_CALL_REQUIRED"
            }
        elif any(k in prompt_lower for k in ["sold", "bought", "receipt", "log sale", "logged sale", "sale", "income", "expense", "spent"]):
            import re
            nums = re.findall(r'r?\s*(\d+(?:\.\d+)?)', prompt_lower)
            amt = float(nums[0]) if nums else 500.0
            return {
                "agent_name": self.name,
                "has_tool_call": True,
                "tool_name": "log_transaction",
                "tool_args": {"description": prompt, "amount": amt, "is_income": True},
                "text": f"ADK Agent '{self.name}' invoked log_transaction tool.",
                "model": self.model,
                "status": "TOOL_CALL_REQUIRED"
            }
        elif any(k in prompt_lower for k in ["sefa loan", "sefa funding", "capital eligibility", "po funding", "microloan"]):
            return {
                "agent_name": self.name,
                "has_tool_call": True,
                "tool_name": "evaluate_capital_eligibility",
                "tool_args": {},
                "text": f"ADK Agent '{self.name}' invoked evaluate_capital_eligibility tool.",
                "model": self.model,
                "status": "TOOL_CALL_REQUIRED"
            }
        else:
            return {
                "agent_name": self.name,
                "has_tool_call": False,
                "tool_name": None,
                "tool_args": {},
                "text": f"Molo! I am the {self.name} agent monitoring your business compliance, SARS TCS status, and municipal tender opportunities in Bloemfontein. How can I assist your business today?",
                "model": self.model,
                "status": "TEXT_RESPONSE"
            }

root_agent = ADKAgent(
    name='root_agent',
    model='openai/gpt-oss-20b',
    instructions=AgentPrompts.MASTER_ORCHESTRATOR,
    description='Master  for SA SMME compliance gap analysis and capital access.',
    tools=[_tender_tools.refresh_sars_tcs, _tender_tools.generate_tender_pack, _tax_tools.log_transaction, _tax_tools.evaluate_capital_eligibility]
)

tender_governance_agent = ADKAgent(
    name='tender_governance_agent',
    model='openai/gpt-oss-20b',
    instructions=AgentPrompts.TENDER_GOVERNANCE_AGENT,
    description='Specialist agent for CSD status, SARS TCS PIN renewals, and municipal tender MBD form packaging.',
    tools=[_tender_tools.refresh_sars_tcs, _tender_tools.generate_tender_pack]
)

tax_financial_agent = ADKAgent(
    name='tax_financial_agent',
    model='openai/gpt-oss-20b',
    instructions=AgentPrompts.TAX_FINANCIAL_AGENT,
    description='Specialist agent for receipt logging, SBC provisional tax estimates, and SEFA loan qualification.',
    tools=[_tax_tools.log_transaction, _tax_tools.evaluate_capital_eligibility]
)