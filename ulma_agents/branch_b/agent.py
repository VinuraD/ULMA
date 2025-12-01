from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from .tools import branch_b_find_user, branch_b_update_role
from ulma_agents.config import config
from ulma_agents.tools import save_step_status

# This agent resides in the Remote Branch.
# It is the GATEKEEPER for all Branch B local operations.
remote_branch_agent = Agent(
    name="branch_b_agent",
    model=config.remote_agent,
    description="The autonomous agent for Branch B. Handles local user management tasks requested by HQ.",
    instruction="""
    You are the Branch B Agent. You operate autonomously in the remote branch.
    
    **Your capabilities:**
    1. You have exclusive access to the local user database (users.json).
    2. You can Find users and Update their roles.

    **Your Workflow:**
    - When HQ asks to "find user X", call `branch_b_find_user`.
    - When HQ asks to "update role for X", call `branch_b_update_role`.
    - Always report back the status (Success/Failure) to the HQ Supervisor.
    - Call `save_step_status(step='remote_delegation', done=True)` when you have completed the request.
    """,
    tools=[
        FunctionTool(branch_b_find_user),
        FunctionTool(branch_b_update_role),
        FunctionTool(save_step_status)
    ],
    output_key="branch_b_response"
)
