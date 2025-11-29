from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from ..config import config
from ..tools import save_step_status

identity_agent = Agent(
    name="identity_agent",
    model=config.identity_agent,
    description="Stub identity agent for directory operations.",
    instruction="""
    You are the identity agent stub. For now, acknowledge the request and
    describe the changes you would apply to the directory (user state, roles,
    groups, apps). When you finish, call save_step_status with step="identity"
    and done=True to mark success. If something looks wrong, call it with
    done=False and explain why in your response.
    """,
    tools=[FunctionTool(save_step_status)],
    output_key="identity_updates",
)
