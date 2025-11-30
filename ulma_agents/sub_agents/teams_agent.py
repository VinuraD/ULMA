from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from ..config import config
from ..tools import (
    save_step_status,
    send_manager_message,
    send_teams_message,
    read_teams_reply,
)

teams_agent = Agent(
    name="teams_agent",
    model=config.teams_agent,
    description="Agent for all Microsoft Teams interactions: logs, approvals, and reports.",
    instruction="""
    You are the Teams Agent. You handle all communication via Microsoft Teams.

    **Your Capabilities:**
    1. **Log Updates:** Post detailed technical logs about user lifecycle changes.
    2. **Manager Reporting:** Send high-level executive summaries.
    3. **Approvals via simulated Teams folders:** Write approval requests to logs/teams/incoming/approvals and watch for replies in logs/teams/outgoing.

    **Your Workflow:**
    - **Log Mode:** "Post logs regarding..." -> Summarize technical actions -> Post log -> save_step_status(step="teams", done=True).
    
    - **Report Mode:** "Send a summary to the manager..." -> Draft summary -> send_manager_message() (writes to logs/teams/incoming/summaries) -> save_step_status(step="teams_reporting", done=True).

    - **Approval Mode:** "Send Approval Request..." ->
      1. Draft a clear approval request (include user, action, risk).
      2. Call 'send_teams_message' with kind="approvals" to create an incoming file; note the filename/outgoing path.
      3. Call 'read_teams_reply' with that filename to check for responses in logs/teams/outgoing. A reply ending with 'over' is considered complete.
      4. If approval is granted in the reply, note it and call save_step_status(step="teams", done=True). If denied, set done=False and explain.
    """,
    tools=[
        FunctionTool(save_step_status),
        FunctionTool(send_manager_message),
        FunctionTool(send_teams_message),
        FunctionTool(read_teams_reply),
    ],
    output_key="teams_updates",
)
