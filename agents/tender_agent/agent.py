from google.adk.agents import Agent
from google.adk.tools import FunctionTool

def check_csd_status(csd_number: str) -> dict:
    return {"csd_number": csd_number, "status": "Active", "compliant": True}

tender_agent = Agent(
    name="tender_agent",
    model="gemini-2.0-flash",
    description="SA tender compliance officer",
    instruction="You are SA tender compliance officer.",
    tools=[FunctionTool(check_csd_status)],
)
