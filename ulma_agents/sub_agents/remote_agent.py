from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from ..config import config
from ..tools import save_step_status

remote_agent = Agent(
    name="remote_branch_agent",
    model=config.remote_agent,
    description="Agent representing an external branch (Branch B). Handles delegated requests.",
    instruction="""
    You are the AI Agent for 'Branch B' (Remote Branch). 
    
    **Your Role:**
    - You receive tasks that are out of scope for the local branch.
    - You act as an independent system.

    **Your Workflow:**
    1. Acknowledge the delegated request from the local supervisor.
    2. Simulate processing the request in your local Branch B systems.
    3. Return a confirmation message (e.g., "Branch B Agent: Request ID #999 processed. User assigned to Branch B group.").
    4. Call 'save_step_status' with step="remote_delegation" and done=True.
    """,
    tools=[FunctionTool(save_step_status)],
    output_key="remote_response",
)

