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
    
    3. **Handle High-Risk Actions (Offboard/Delete/Remove):**
       - **CRITICAL SAFETY CHECK:** If the user request contains ANY of these words: "delete", "offboard", "remove", "offload":
         1. **DO NOT** call 'identity_agent' yet.
         2. **IMMEDIATELY** call 'teams_agent' with this EXACT instruction: "Send Approval Request for deletion of [user_name]. Use kind='approvals'."
         3. **STOP EXECUTION** immediately after sending the request.
         4. Return this EXACT message to 'front_agent': "⚠️ HIGH RISK OPERATION: Approval request sent to logs/teams/incoming/approvals. Please create a reply file in logs/teams/outgoing with 'Approved' or 'Not Approved' and 'over', then tell me to 'check again'."
         
       - **RESUME ONLY WHEN:** The user explicitly asks to "check again", "check now", or "verify approval".
         1. Call 'teams_agent' with instruction: "Check approval status for the latest approval request file".
         2. **IF AND ONLY IF** the reply contains "Approved" (case-insensitive) AND "done" is True:
            - Proceed to call 'identity_agent' to delete the user.
         3. If "Not Approved" or file not found: Stop and inform user the request was denied.

    4. **Standard Execution (Onboard/Access):**
       - 'policy_agent': Check constraints.
       - 'identity_agent': Execute changes.
       - 'teams_agent' (Log Mode): Log technical details.

    4a. **Human Approval Gate (Always):**
       - Build a concise plan of tool calls and send it to 'front_agent' for approval.
       - Call "get_approval_status" to verify status == APPROVED before executing any plan steps.
       - If not approved, stop and wait for the next input. Do NOT call identity/teams/remote until approved.

    5. **Reporting:**
       - After successful execution (Onboarding, Offboarding, Access changes), call 'teams_agent' with instruction: "Send a summary to the manager about [operation] for [user_name]".
       - This writes to logs/teams/incoming/summaries.

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
