from google.adk.agents import Agent
tax_agent = Agent(
    name="tax_agent",
    model="gemini-2.0-flash",
    instruction="SA tax helper.",
)
