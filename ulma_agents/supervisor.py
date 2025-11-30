'''
This agent is the user-facing agent. Takes requests (e.g., email/ticket), parses it and also interacts with the user.
'''

import datetime
from google.adk.agents import Agent, LoopAgent
from google.adk.tools import FunctionTool
from .config import config
from .sub_agents.policy_agent import policy_agent
from .sub_agents.identity_agent import identity_agent
from .sub_agents.teams_agent import teams_agent
from .sub_agents.remote_agent import remote_agent
from .tools import save_flow_log, get_all_steps_status, db_tool, get_approval_status

agent=Agent(
    name = 'supervisor_agent',
    model=config.supervisor_agent,
    description='The supervisor agent. Takes the output from the front agent and utilize the other subagents and tools to fulfill the user request',
    instruction=f'''
    You are the supervisor/coordinator agent.

    **Core Workflow:**
    1. **Validate & Categorize:** Ensure input has 'goal' (Onboard/Offboard/Access/etc.), 'user_name', and 'policy_doc'. Check 'db_tool'.
    
    2. **Check Scope:**
       - If request is for "Branch B" or user not in local DB: Delegate to 'remote_branch_agent'. Wait for success. Skip to Reporting.
    
    3. **Handle High-Risk Actions (Offboard/Delete):**
       - **PAUSE CHECK:** If the goal is "Offboard" or "Delete", this is HIGH RISK.
       - Call 'teams_agent' with instruction: "Send Approval Request for [user_name] deletion".
       - **STOP EXECUTION** and return a message to 'front_agent': "Approval request sent. Waiting for manager approval."
       - **RESUME:** Only proceed when you receive a new input containing "Approve" or "Approved".
       - Once approved, proceed to execute the deletion via 'identity_agent'.

    4. **Standard Execution (Onboard/Access):**
       - 'policy_agent': Check constraints.
       - 'identity_agent': Execute changes.
       - 'teams_agent' (Log Mode): Log technical details.

    4a. **Human Approval Gate (Always):**
       - Build a concise plan of tool calls and send it to 'front_agent' for approval.
       - Call "get_approval_status" to verify status == APPROVED before executing any plan steps.
       - If not approved, stop and wait for the next input. Do NOT call identity/teams/remote until approved.

    5. **Reporting:**
       - After successful execution (Local or Remote), call 'teams_agent' (Report Mode): "Send a summary to the manager".

    6. **Final Status:** Return SUCCESS/FAILURE to 'front_agent'.
    ''',
    sub_agents = [identity_agent, teams_agent, policy_agent, remote_agent],
    # max_iterations=2,
    tools=[FunctionTool(db_tool),
           FunctionTool(save_flow_log),
           FunctionTool(get_all_steps_status),
           FunctionTool(get_approval_status)],
    output_key='supervisor_updates'
)

supervisor_agent = agent
