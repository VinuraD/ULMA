import os
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams
from ..config import config
from ..tools import save_step_status, send_manager_message

# Connect to the Azure MCP server (SSE transport). Override with AZURE_MCP_SSE_URL if needed.
AZURE_MCP_SSE_URL = os.getenv("AZURE_MCP_SSE_URL", "http://localhost:8001/sse")
azure_mcp_toolset = McpToolset(
    connection_params=SseConnectionParams(
        url=AZURE_MCP_SSE_URL,
    ),
    tool_name_prefix="azure",  # keep names obvious in traces
)

identity_agent = Agent(
    name="identity_agent",
    model=config.identity_agent,
    description="Identity agent for Entra ID operations via Azure MCP.",
    instruction="""
<<<<<<< HEAD
    You are the identity agent stub. For now, acknowledge the request and
    describe the changes you would apply to the directory (user state, roles,
    groups, apps).

    Always summarize what was done (or attempted) for the manager by calling
    'send_manager_message' with a brief, executive-friendly update. This writes
    a text file under logs/teams/incoming/summaries.

    When you finish, call save_step_status with step="identity" and done=True to
    mark success. If something looks wrong, call it with done=False and explain
    why in your response, and still send a manager summary noting the issue.
    """,
    tools=[FunctionTool(save_step_status), FunctionTool(send_manager_message)],
=======
    You are the identity agent. Use the Azure MCP tools to read or change Entra ID.

    Available MCP tools (prefixed with `azure_`):
      - azure_get_user(upn)
      - azure_create_user(upn, display_name, password)
      - azure_add_user_to_group(user_upn, group_id)
      - azure_delete_user(upn_or_id)
      - azure_reset_user_password(upn, new_password, force_change_next_sign_in=True)

    Workflow:
      1) Understand the requested action (onboard/offboard/access/password).
      2) Call the appropriate Azure MCP tool(s). Avoid hallucinating values; use provided goal/user/role/apps/groups.
      3) Summarize what was done (or why it failed).
      4) Call save_step_status(step="identity", done=True) on success; use done=False if any operation failed or was skipped.
    """,
    tools=[azure_mcp_toolset, FunctionTool(save_step_status)],
>>>>>>> a68f4d4 (azure updates)
    output_key="identity_updates",
)
