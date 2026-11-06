import os
import sys
from typing import Dict, Any, Optional
import streamlit as st

# Safe import resolution for modular or flat layouts
try:
    from agents.prompts import AgentPrompts
    from agents.adk_agent import ADKAgent
except ImportError:
    from prompts import AgentPrompts
    from adk_agent import ADKAgent


class GeminiClient:
    """Gemini & Groq Client wrapping Google ADK Agent import and tool function calls."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "openai/gtp-oss-20b"):
        # Safe API Key retrieval (Env Vars -> Streamlit Secrets -> None)
        
        resolved_key =  st.secrets.get("GROQ_API_KEY")
            

        self.api_key = resolved_key
        self.model_name = model_name

        # Initialize ADK Agent safely
        self.agent = ADKAgent(
            name="MasterOrchestrator",
            model=self.model_name,
            instructions=AgentPrompts.MASTER_ORCHESTRATOR,
            api_key=self.api_key
        )

    def parse_gemini_response(self, prompt: str, profile_summary: str) -> Dict[str, Any]:
        """Execute ADK Agent invocation passing prompt and profile summary context."""
        agent_result = self.agent.run(prompt, context={"summary": profile_summary}) or {}

        if agent_result.get("has_tool_call"):
            return {
                "tool_name": agent_result.get("tool_name"),
                "args": agent_result.get("tool_args", {}),
                "model_name": self.model_name,
                "agent_name": agent_result.get("agent_name", "MasterOrchestrator")
            }
        else:
            return {
                "text": agent_result.get("text", ""),
                "model_name": self.model_name,
                "agent_name": agent_result.get("agent_name", "MasterOrchestrator")
            }